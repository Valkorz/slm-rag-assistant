# SLM-RAG-ASSISTANT

This project implements a Small Language Model interface that uses RAG (Retrieval Augmented Generation) to extract data from a ChromaDB database based on context. 

---

## 💻 Setup

This project was created using `Python 3.12.6` and a list of libraries disclosed within `requirements.txt`. The small-language-models used were downloaded from `huggingface.co` and hosted locally using the `LLama` library. The following steps are necessary to execute this project:

1. **Visit Huggingface.co**

    [HuggingFace](https://huggingface.co/models) is an online community that allows the download of Large Language Models, as `.GGUF` files, used for local hosting. **IMPORTANT:** You must download the GGUF files as they are quantized vesions of the model, with higher efficiency and lower hardware requirement.

2. **Download the Small Language Models**

    **IMPORTANT: Download the files that contain tags such as 'Q4_K' in the name, which stand for quantization level. Quantized models are lighter and faster.**
    
    From within the HuggingFace interface, download the following models:
    - [meta-llama-3.1-8b-instruct](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct)
    - [deepseek-r1-distill-qwen-1.5b](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B)

    Alternatively, for a broader language support, you can use these models:
    - [google/gemma-4-e2b](https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/tree/main)
    - [google/gemma-4-e4b](https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/tree/main)

    The following image illustrates the download procedure:
    ![Downloading models from huggingface](docs/images/huggingface-modeldownload.png)

    After downloading the models, create a designated folder on your computer for storing them.

3. **Install required libraries**

    This project uses several libraries, ranging from `openai` for endpoint communication to `chromadb` for context window management.
    Open the terminal within the project folder and execute the following command:
    ```
        pip install -r requirements.txt 
    ```
    This will install all necessary dependencies explicitly stated within the requirements file.
    These are the required libraries:

    ```
        chromadb>=0.5.23
        sentence-transformers>=3.2.1
        openai>=2.24.0
        llama-cpp-python>=0.2.0
        huggingface-hub>=0.24.0

        pymupdf>=1.27.2.2
        langchain_text_splitters>=1.1.1

        pillow>=11.2.1
        customtkinter>=5.2.0
    ```

4. **Interface initialization and usage**
    To execute the project, you must ensure you have Python at version `3.12.6` or above, then simply execute the `assistant.py` script, which initiates a TKinter window. 
    Inside the running instance, the user is able to select documents from the desktop, change the model's language and perform a question, which will be answered by the model based on the contents found within the source files. 
    The first initialization may take a while.
    **IMPORTANT: You must select a folder that contains your .GGUF files and then select a query and reasoning model.**
    The following image showcases an usage example for the assistant.

    ![Application instance](docs/images/assistant.png)

    The picture shows the TKinter interface being executed. The user has selected a document named: `Uncertainty_principle....pdf`, and asked the following question: "What does the wave of a particle have to do with the uncertainty principle?". After roughly 1 minute and 30 seconds, the assistant read the PDF, chunkized it into the database and provided a matching chunk as a response. The model did not invent anything as the response is exactly as present inside the source material:

    ![Source material](docs/images/source-material.png)

5. **(OPTIONAL) Prompting the model through TCP commands:**
    Additionally, you can operate the application through TCP commands, which are processed and the received data is appended to the interface. 
    In order to start the TCP server for the application, you must flip the 'TCP' switch, as per shown in the following image:
    ![Server activation switch](docs/images/tcp-switch.png)

    The usage is done by sending a TCP packet to the open port using the following JSON format:

    ```
    {
        "question":"your question"
    }
    ```

## ⚙️ Hardware

The hardware used during the development of this project contains the following specifications:

- **GPU:** RTX 2050 (4GB RAM)
- **CPU:** Intel I5-12450H 
- **RAM:** 16 GB DDR5
- **STORAGE:** 1TB SSD

---

## 💡 Purpose of this project

Text processing and analysis is one of the cornerstone applications of language models, however, adopting privately hosted Large Language Models (LLMs) for this task brings forth relevant privacy concerns. How can we ensure our data is being processed in a secure and private manner whilst being decoupled from a private ecossystem?
This project addresses these concerns by leveraging small language models (SLMs) with local deployment, ensuring data remains under user control. For comprehensive insights into LLM privacy risks, see [Beyond Data Privacy: New Privacy Risks for Large Language Models](https://doi.org/10.1145/3605764.3623951) by Du, Li, Li, and Ding (Purdue University).

This project was implemented with consumer-grade hardware in mind, ensuring that language models will run cheaply and quickly on less capable devices, while mitigating the common issues (eg. hallucinations) by using **Retrieval Augmented Generation (RAG)** to ensure consistent and trustworthy responses.


