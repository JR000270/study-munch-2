import React from 'react';
import './App.css';
import { motion } from "motion/react"
import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';



function AppContent() {
  return ( 
    <div className="bg-black">

      <main>

        <div>
          <h1 className=" text-4xl text-orange-500 font-display font-bold" >Study Munch</h1>
        </div>

         {/* <div className="flex-1 overflow-y-auto no-scrollbar px-4 lg:px-15 py-6 lg:pb-12">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/sign In" element={<SignIn />} />
            <Route path="/topic" element={<Topic />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/quiz" element={<Quiz />} />
            <Route path="/flashcards" element={<Flashcards />} />
            <Route path="/context" element={<Context />} />
            <Route path="/user" element={<User />} />
           
          </Routes>
        </div> */}

      </main>
    </div>
    

  )
}

export default function App(){
  return(
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  )
};