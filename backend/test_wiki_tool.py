from wiki_search_tool import make_wiki_search_tool 

wiki_tool = make_wiki_search_tool()

print(wiki_tool.call(query="Halloween").content) #should get results about Halloween
print("-----")
print(wiki_tool.call(query="Doritos color").content) 
print("-----")
print(wiki_tool.call(query="xqzvbnmlkj").content)  #should hit NO_WIKI_RESULTS