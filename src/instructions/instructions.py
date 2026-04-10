#This class is used to define different instructions for different languages
class Instructions:
    _language : str

    def __init__(self, lang : str):
        self._language = lang
        pass

    def get_queryInstruction(self, n_queries : int, user_question : str) -> str:
        if self._language.upper() == "EN":
            return self._instQueries_EN(n_queries, user_question)
        elif self._language.upper() == "PTBR":
            return self._instQueries_PTBR(n_queries, user_question)
        else: return "AN ERROR OCCURED WITH THE REQUEST. PLEASE REPORT THIS."

    def get_promptInstruction(self, context : str, user_question : str) -> str:
        if self._language.upper() == "EN":
            return self._instPrompt_EN(context, user_question)
        elif self._language.upper() == "PTBR":
            return self._instPrompt_PTBR(context, user_question)
        else: return "AN ERROR OCCURED WITH THE REQUEST. PLEASE REPORT THIS."

    def get_responseFormat(self) -> dict[str, object]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "reasoning_response",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "queries": {"type": "array"},
                    },
                    "required": ["queries"],
                    "additionalProperties": False
                }
            }
        }

    #English
    def _instQueries_EN(self, n_queries : int, user_question : str) -> str:
        return f"""<|im_start|>system
        Output ONLY a JSON array. No text before or after. No explanation.<|im_end|>
        <|im_start|>user
        Generate {n_queries} short search queries (5-10 words each) to find information answering this question.

        Example input: "What are the tax brackets for 2024?"
        Example output: ["tax brackets 2024", "income tax rates federal", "IRS tax table current year"]

        Now generate for:
        Question: {user_question}
        Output:<|im_end|>
        <|im_start|>assistant
        ["""
    
    def _instPrompt_EN(self, context : str, user_question : str) -> str:
        return f"""
        You are a document assistant. Answer the user's question using ONLY the sources below.
        If the answer is not in the sources, reply: "Information not found within the provided sources."
        Always end your answer with a line starting with "Source:" citing which source(s) you used.

        {context}

        Question: {user_question}
        Answer:
        """

    #Portuguese
    def _instQueries_PTBR(self, n_queries : int, user_question : str) -> str:
        return f"""
        Você é um gerador de consultas de pesquisa.
        Seu trabalho é produzir {n_queries} consultas pequenas que irão ajudar encontrar informaçõess para responder a pergunta do usuário.

        Regras:
        - Cada consulta deve ser curta (5-10 palavras no máximo).
        - Consultas devem ser no mesmo idioma que a questão.
        - A saída (output) deve ser APENAS um JSON ARRAY de strings, nada mais.
        - Sem explicações 

        Questão do usuário: {user_question}

        JSON ARRAY de consultas de pesquisa:
        """
         
    def _instPrompt_PTBR(self, context : str, user_question : str) -> str:
        return f"""
        Você é um assistente de documentos. Responda a pergunta do usuário com APENAS as fontes abaixo.
        Se a resposta não pode ser encontrada nas fontes, responda: "Nenhuma informação relevante encontrada nos documentos."
        Sempre termine a sua resposta com "Fontes: " e a seguir detalhando todas as fontes utilizadas na resposta.

        {context}

        Pergunta: {user_question}
        Resposta:
        """
    
