from src.model import Model

model = Model(query_count=5,lang="EN")
# print(model._queryMemories("How does the IRS protect my privacy?"))
print(model.prompt("How does the IRS protect my privacy?"))
