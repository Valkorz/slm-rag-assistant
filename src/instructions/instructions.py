# This class is used to define different instructions for different languages
class Instructions:
    _language: str
    _mode: str  # "Exact" | "Adaptive"

    LANGUAGES = ["EN", "PTBR"]
    MODES = ["Exact", "Adaptive"]

    # Placeholder strings used in the JSON structure examples. The model must
    # replace them; model.py checks answers against these to detect template echo.
    PLACEHOLDER_ANSWERS = ["your final answer here", "sua resposta final aqui"]

    def __init__(self, lang: str, mode: str = "Exact"):
        self._language = lang.upper() if lang.upper() in self.LANGUAGES else "EN"
        self._mode = mode.capitalize() if mode.capitalize() in self.MODES else "Exact"

    def set_language(self, lang: str):
        if lang.upper() in self.LANGUAGES:
            self._language = lang.upper()

    def set_mode(self, mode: str):
        if mode.capitalize() in self.MODES:
            self._mode = mode.capitalize()

    def get_queryInstruction(self, n_queries: int, user_question: str) -> str:
        if self._language == "PTBR":
            return self._instQueries_PTBR(n_queries, user_question)
        return self._instQueries_EN(n_queries, user_question)

    def get_promptInstruction(self, context: str, user_question: str) -> str:
        if self._mode == "Adaptive":
            if self._language == "PTBR":
                return self._instPrompt_Adaptive_PTBR(context, user_question)
            return self._instPrompt_Adaptive_EN(context, user_question)
        if self._language == "PTBR":
            return self._instPrompt_PTBR(context, user_question)
        return self._instPrompt_EN(context, user_question)

    def get_errSources(self) -> str:
        if self._language == "PTBR":
            return self._errSources_PTBR()
        return self._errSources_EN()

    def get_queryResponseFormat(self, n_queries: int) -> dict:
        return {
            "type": "object",
            "properties": {
                "thought_process": {"type": "string"},
                "queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": n_queries,
                    "maxItems": n_queries
                }
            },
            "required": ["thought_process", "queries"],
            "additionalProperties": False
        }

    def get_promptResponseFormat(self) -> dict:
        """JSON schema for the answer generation step.

        'thought_process' comes first so the model reasons over the sources
        before committing to an answer.
        """
        return {
            "type": "object",
            "properties": {
                "thought_process": {"type": "string"},
                "answer": {"type": "string"},
                "sources": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["thought_process", "answer", "sources"],
            "additionalProperties": False
        }

    # ── English ───────────────────────────────────────────────────────────────

    def _instQueries_EN(self, n_queries: int, user_question: str) -> str:
        query_slots = ", ".join(f'"query {i + 1}"' for i in range(n_queries))
        return (
            f"### TASK\n"
            f"Generate exactly {n_queries} short search queries for a semantic search "
            f"over documents, to retrieve passages that answer the question below.\n\n"
            f"### QUERY RULES\n"
            f"- ALL queries must be written in ENGLISH. No other language.\n"
            f"- Each query must be 3-8 words. No filler words.\n"
            f"- Use correct spelling throughout.\n"
            f"- Each query MUST cover a DIFFERENT angle of the question, for example:\n"
            f"  1. the main concept stated directly;\n"
            f"  2. a rephrasing using synonyms or related terms;\n"
            f"  3. how it works / its mechanism;\n"
            f"  4. applications, examples or consequences;\n"
            f"  5. broader context or closely related concepts.\n"
            f"- No two queries may share the same pair of main words.\n"
            f"- Use terms likely to appear in the documents themselves.\n\n"
            f"### OUTPUT FORMAT — STRICT\n"
            f"Your ENTIRE response must be a single, valid JSON object — no text before or "
            f"after it, no markdown code blocks, no extra fields.\n"
            f"Required structure:\n"
            f"{{\n"
            f'  "thought_process": "one short sentence on how you varied the queries",\n'
            f'  "queries": [{query_slots}]\n'
            f"}}\n\n"
            f"### EXAMPLE (unrelated topic — copy the FORMAT only, never the content)\n"
            f"Question: How does photosynthesis work in plants?\n"
            f"{{\n"
            f'  "thought_process": "Covered the definition, the mechanism in other words, and a key component.",\n'
            f'  "queries": ["photosynthesis process definition", "how plants convert sunlight into energy", "chlorophyll role in light absorption"]\n'
            f"}}\n"
            f"The example shows 3 queries; YOU must output exactly {n_queries}.\n\n"
            f"### YOUR TURN\n"
            f"Question: {user_question}\n"
            f"Respond with the JSON object only."
        )

    def _instPrompt_EN(self, context: str, user_question: str) -> str:
        return (
            f"### ROLE\n"
            f"You are a document assistant. Answer the question using ONLY the "
            f"information in the sources below.\n\n"
            f"### HOW TO ANSWER\n"
            f"- First, in 'thought_process', note briefly (under 60 words) which sources "
            f"contain information relevant to the question and what they say.\n"
            f"- Then write 'answer': its FIRST sentence must directly answer the question. "
            f"Do not restate the question, do not describe what the sources are about — answer it.\n"
            f"- Write the answer in English, in your own words, clean and direct.\n"
            f"- If the sources only partially answer, give the partial information you have.\n"
            f"- Set 'answer' to exactly '{self._errSources_EN()}' (and 'sources' to []) ONLY "
            f"when none of the sources relate to the topic of the question.\n"
            f"- 'sources' must list every source used, e.g. \"file.pdf p.3\".\n"
            f"- Replace every placeholder (e.g. \"your final answer here\") with real "
            f"content. NEVER output placeholder text literally.\n\n"
            f"### OUTPUT FORMAT — STRICT\n"
            f"Your ENTIRE response must be a single, valid JSON object — no text before or "
            f"after it, no markdown code blocks, no extra fields.\n"
            f"Required structure:\n"
            f"{{\n"
            f'  "thought_process": "which sources are relevant and what they say",\n'
            f'  "answer": "your final answer here",\n'
            f'  "sources": ["file.pdf p.X", "file.pdf p.Y"]\n'
            f"}}\n\n"
            f"### SOURCES\n"
            f"{context}\n\n"
            f"### QUESTION\n"
            f"{user_question}\n\n"
            f"Respond with the JSON object only."
        )

    def _instPrompt_Adaptive_EN(self, context: str, user_question: str) -> str:
        return (
            f"### ROLE\n"
            f"You are an analytical assistant. Answer the question using ONLY the "
            f"information in the sources below, but reason actively over them: combine "
            f"facts from multiple sources, perform calculations, and draw logical "
            f"inferences when the question requires it. Adapt to whatever domain the "
            f"sources cover.\n\n"
            f"### HOW TO ANSWER\n"
            f"- First, in 'thought_process', note briefly (under 60 words) which sources are "
            f"relevant and what reasoning or calculation the question needs.\n"
            f"- Then write 'answer': its FIRST sentence must directly answer the question. "
            f"Include the calculation or deduction steps when relevant.\n"
            f"- Write the answer in English, in your own words.\n"
            f"- Base everything on the source data. Do not invent numbers or facts.\n"
            f"- Set 'answer' to exactly '{self._errSources_EN()}' (and 'sources' to []) ONLY "
            f"when the TOPIC of the question appears in no source. If the sources contain "
            f"data that allows answering through reasoning, answer using that data.\n"
            f"- 'sources' must list every source used, e.g. \"file.pdf p.3\".\n"
            f"- Replace every placeholder (e.g. \"your final answer here\") with real "
            f"content. NEVER output placeholder text literally.\n\n"
            f"### OUTPUT FORMAT — STRICT\n"
            f"Your ENTIRE response must be a single, valid JSON object — no text before or "
            f"after it, no markdown code blocks, no extra fields.\n"
            f"Required structure:\n"
            f"{{\n"
            f'  "thought_process": "which sources are relevant and what reasoning applies",\n'
            f'  "answer": "your final answer here",\n'
            f'  "sources": ["file.pdf p.X", "file.pdf p.Y"]\n'
            f"}}\n\n"
            f"### EXAMPLE (unrelated domain — copy the FORMAT only, never its text or numbers)\n"
            f"Sources: [Source 1 | manual.pdf p.2] The tank holds 40 liters. The car consumes 8 liters per 100 km.\n"
            f"Question: How far can the car travel on a full tank?\n"
            f"{{\n"
            f'  "thought_process": "Source 1 gives tank capacity (40 L) and consumption (8 L/100 km). Range = 40 / 8 x 100.",\n'
            f'  "answer": "The car can travel about 500 km on a full tank: 40 liters / 8 L per 100 km = 500 km.",\n'
            f'  "sources": ["manual.pdf p.2"]\n'
            f"}}\n\n"
            f"### SOURCES\n"
            f"{context}\n\n"
            f"### QUESTION\n"
            f"{user_question}\n\n"
            f"Respond with the JSON object only."
        )

    def _errSources_EN(self) -> str:
        return "Information not found within provided data."

    # ── Portuguese ────────────────────────────────────────────────────────────

    def _instQueries_PTBR(self, n_queries: int, user_question: str) -> str:
        query_slots = ", ".join(f'"consulta {i + 1}"' for i in range(n_queries))
        return (
            f"### TAREFA\n"
            f"Gere exatamente {n_queries} consultas de pesquisa curtas para uma busca "
            f"semântica em documentos, de modo a recuperar trechos que respondam a "
            f"pergunta abaixo.\n\n"
            f"### REGRAS DAS CONSULTAS\n"
            f"- TODAS as consultas devem ser escritas em PORTUGUÊS DO BRASIL. Nenhum outro idioma.\n"
            f"- Cada consulta deve ter de 3 a 8 palavras. Sem palavras de preenchimento.\n"
            f"- Escreva com ortografia correta, INCLUINDO acentos e cedilha "
            f"(ex.: escreva \"computação quântica\", NUNCA \"computacao quantica\"). "
            f"Consultas sem acentos prejudicam a busca.\n"
            f"- Cada consulta DEVE cobrir um ângulo DIFERENTE da pergunta, por exemplo:\n"
            f"  1. o conceito principal de forma direta;\n"
            f"  2. uma reformulação com sinônimos ou termos relacionados;\n"
            f"  3. como funciona / o mecanismo;\n"
            f"  4. aplicações, exemplos ou consequências;\n"
            f"  5. contexto mais amplo ou conceitos próximos.\n"
            f"- Duas consultas não podem repetir o mesmo par de palavras principais.\n"
            f"- Use termos que provavelmente aparecem nos próprios documentos.\n\n"
            f"### FORMATO DE SAÍDA — ESTRITO\n"
            f"Sua resposta COMPLETA deve ser um único objeto JSON válido — nenhum texto "
            f"antes ou depois, sem blocos de código markdown, sem campos extras.\n"
            f"Estrutura obrigatória:\n"
            f"{{\n"
            f'  "thought_process": "uma frase curta sobre como você variou as consultas",\n'
            f'  "queries": [{query_slots}]\n'
            f"}}\n\n"
            f"### EXEMPLO (tema não relacionado — copie apenas o FORMATO, nunca o conteúdo)\n"
            f"Pergunta: Como funciona a fotossíntese nas plantas?\n"
            f"{{\n"
            f'  "thought_process": "Cobri a definição, o mecanismo com outras palavras e um componente-chave.",\n'
            f'  "queries": ["fotossíntese definição processo", "como plantas convertem luz solar em energia", "papel da clorofila na absorção de luz"]\n'
            f"}}\n"
            f"O exemplo mostra 3 consultas; VOCÊ deve produzir exatamente {n_queries}.\n\n"
            f"### SUA VEZ\n"
            f"Pergunta: {user_question}\n"
            f"Responda apenas com o objeto JSON."
        )

    def _instPrompt_PTBR(self, context: str, user_question: str) -> str:
        return (
            f"### FUNÇÃO\n"
            f"Você é um assistente de documentos. Responda a pergunta usando APENAS as "
            f"informações das fontes abaixo.\n\n"
            f"### COMO RESPONDER\n"
            f"- Primeiro, em 'thought_process', anote brevemente (menos de 60 palavras) quais "
            f"fontes contêm informações relevantes para a pergunta e o que elas dizem.\n"
            f"- Depois escreva 'answer': a PRIMEIRA frase deve responder diretamente a pergunta. "
            f"Não repita a pergunta, não descreva sobre o que as fontes falam — responda.\n"
            f"- Escreva a resposta em português do Brasil, com suas próprias palavras, de forma limpa e direta.\n"
            f"- Se as fontes respondem só parcialmente, dê a informação parcial que houver.\n"
            f"- Defina 'answer' como exatamente '{self._errSources_PTBR()}' (e 'sources' como []) "
            f"SOMENTE quando nenhuma fonte tiver relação com o assunto da pergunta.\n"
            f"- 'sources' deve listar todas as fontes usadas, ex.: \"arquivo.pdf p.3\".\n"
            f"- Substitua todo texto de exemplo (ex.: \"sua resposta final aqui\") por conteúdo "
            f"real. NUNCA escreva o texto de exemplo literalmente.\n\n"
            f"### FORMATO DE SAÍDA — ESTRITO\n"
            f"Sua resposta COMPLETA deve ser um único objeto JSON válido — nenhum texto "
            f"antes ou depois, sem blocos de código markdown, sem campos extras.\n"
            f"Estrutura obrigatória:\n"
            f"{{\n"
            f'  "thought_process": "quais fontes são relevantes e o que dizem",\n'
            f'  "answer": "sua resposta final aqui",\n'
            f'  "sources": ["arquivo.pdf p.X", "arquivo.pdf p.Y"]\n'
            f"}}\n\n"
            f"### FONTES\n"
            f"{context}\n\n"
            f"### PERGUNTA\n"
            f"{user_question}\n\n"
            f"Responda apenas com o objeto JSON."
        )

    def _instPrompt_Adaptive_PTBR(self, context: str, user_question: str) -> str:
        return (
            f"### FUNÇÃO\n"
            f"Você é um assistente analítico. Responda a pergunta usando APENAS as "
            f"informações das fontes abaixo, mas raciocine ativamente sobre elas: combine "
            f"fatos de várias fontes, faça cálculos e tire inferências lógicas quando a "
            f"pergunta exigir. Adapte-se ao domínio das fontes, seja ele qual for.\n\n"
            f"### COMO RESPONDER\n"
            f"- Primeiro, em 'thought_process', anote brevemente (menos de 60 palavras) quais "
            f"fontes são relevantes e qual raciocínio ou cálculo a pergunta exige.\n"
            f"- Depois escreva 'answer': a PRIMEIRA frase deve responder diretamente a pergunta. "
            f"Inclua as etapas do cálculo ou dedução quando for relevante.\n"
            f"- Escreva a resposta em português do Brasil, com suas próprias palavras.\n"
            f"- Baseie tudo nos dados das fontes. Não invente números nem fatos.\n"
            f"- Defina 'answer' como exatamente '{self._errSources_PTBR()}' (e 'sources' como []) "
            f"SOMENTE se o ASSUNTO da pergunta não aparecer em nenhuma fonte. Se as fontes "
            f"contêm dados que permitem responder com raciocínio, responda usando esses dados.\n"
            f"- 'sources' deve listar todas as fontes usadas, ex.: \"arquivo.pdf p.3\".\n"
            f"- Substitua todo texto de exemplo (ex.: \"sua resposta final aqui\") por conteúdo "
            f"real. NUNCA escreva o texto de exemplo literalmente.\n\n"
            f"### FORMATO DE SAÍDA — ESTRITO\n"
            f"Sua resposta COMPLETA deve ser um único objeto JSON válido — nenhum texto "
            f"antes ou depois, sem blocos de código markdown, sem campos extras.\n"
            f"Estrutura obrigatória:\n"
            f"{{\n"
            f'  "thought_process": "quais fontes são relevantes e qual raciocínio se aplica",\n'
            f'  "answer": "sua resposta final aqui",\n'
            f'  "sources": ["arquivo.pdf p.X", "arquivo.pdf p.Y"]\n'
            f"}}\n\n"
            f"### EXEMPLO (domínio não relacionado — copie apenas o FORMATO, nunca o texto ou os números)\n"
            f"Fontes: [Fonte 1 | manual.pdf p.2] O tanque comporta 40 litros. O carro consome 8 litros a cada 100 km.\n"
            f"Pergunta: Que distância o carro percorre com o tanque cheio?\n"
            f"{{\n"
            f'  "thought_process": "A Fonte 1 dá a capacidade do tanque (40 L) e o consumo (8 L/100 km). Autonomia = 40 / 8 x 100.",\n'
            f'  "answer": "O carro percorre cerca de 500 km com o tanque cheio: 40 litros / 8 L por 100 km = 500 km.",\n'
            f'  "sources": ["manual.pdf p.2"]\n'
            f"}}\n\n"
            f"### FONTES\n"
            f"{context}\n\n"
            f"### PERGUNTA\n"
            f"{user_question}\n\n"
            f"Responda apenas com o objeto JSON."
        )

    def _errSources_PTBR(self) -> str:
        return "Nenhuma informação encontrada."
