import random
from dataclasses import dataclass

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from llama_index.core.prompts import PromptTemplate
from llama_index.llms.openai import OpenAI

from tools.passages import Passage, format_passages

load_dotenv("keys.env")

NUM_OPTIONS = 4                 # 1 correct + 3 wrong
QUESTIONS_PER_PASSAGE = 1       # MCQs cost more to write well than flashcards, so fewer per passage
MIN_QUESTIONS, MAX_QUESTIONS = 3, 20


def plan_question_count(num_passages: int, requested: int | None = None) -> int:
    """Use the user's requested count if given, otherwise scale with content, always clamped."""
    n = requested if requested is not None else num_passages * QUESTIONS_PER_PASSAGE
    return max(MIN_QUESTIONS, min(MAX_QUESTIONS, n))


# ---------- The contract with the LLM ----------
class QuestionDraft(BaseModel):
    question: str = Field(description="The question. Tests one idea, under 30 words.")
    correct_answer: str = Field(description="The one correct answer, stated directly by the passage.")
    wrong_answers: list[str] = Field(
        description="Exactly 3 wrong answers. Each must be plausible to someone who hasn't "
                    "studied, about the same length and style as the correct answer, and clearly "
                    "wrong according to the passage."
    )
    passage: int = Field(description="The number of the passage this question is based on.")


class QuizDraft(BaseModel):
    questions: list[QuestionDraft]


QUIZ_PROMPT = PromptTemplate(
    """You are writing a multiple-choice quiz from the numbered passages below.

Rules:
- Write {num_questions} questions, spread across the passages rather than taken from just one.
- Each question tests ONE fact or idea that its passage states directly. Do not add outside knowledge.
- Prefer understanding (causes, definitions, relationships, key dates) over trivia.
- Wrong answers should be believable: use related terms, nearby dates, or other names from the
  passages. Never use "All of the above", "None of the above", or joke answers.
- The question wording must not give away the answer.
- Ignore citation markers like [12], page furniture, and navigation text.
- No two questions should test the same fact.
- Set `passage` to the number of the passage each question comes from.
- Keep the correct answer short (under 12 words). Write wrong answers with the same length,
  grammatical form, and level of detail as the correct answer.
- Never use words like "only", "always", or "never" in wrong answers unless the correct
  answer uses them too. They make wrong answers easy to spot.

Passages:
{passages}
"""
)


# ---------- What the rest of the app gets back ----------
@dataclass
class GeneratedQuestion:
    question: str
    options: list[str]  #shuffled answer choices
    correct_index: int  #which one is right
    source_label: str   #to know where it came from    


def generate_quiz(passages: list[Passage], num_questions: int, callback_manager = None) -> list[GeneratedQuestion]:
    if not passages:
        raise ValueError("No content to make a quiz from")

    llm = OpenAI(model="gpt-4.1", callback_manager=callback_manager, temperature=0.3)
    draft = llm.structured_predict(
        QuizDraft,
        QUIZ_PROMPT,
        num_questions=num_questions,
        passages=format_passages(passages),
    )

    questions, seen_questions = [], set()
    for d in draft.questions:
        text = d.question.strip()
        correct = d.correct_answer.strip()
        if not text or not correct:
            continue
        if not 1 <= d.passage <= len(passages):
            continue
        if text.lower() in seen_questions:
            continue

        # Keep only wrong answers that are non-empty and not duplicates (of each other or the correct one)
        used = {correct.lower()}
        wrong = []
        for w in d.wrong_answers:
            w = w.strip()
            if w and w.lower() not in used:
                used.add(w.lower())
                wrong.append(w)
        if len(wrong) < NUM_OPTIONS - 1:
            continue   # not enough real options, so drop it rather than ship a 2-option question

        options = [correct] + wrong[: NUM_OPTIONS - 1]
        random.shuffle(options)

        seen_questions.add(text.lower())
        questions.append(GeneratedQuestion(
            question=text,
            options=options,
            correct_index=options.index(correct),   # safe: options are unique after the filter above
            source_label=passages[d.passage - 1].label,
        ))
    return questions[:num_questions]