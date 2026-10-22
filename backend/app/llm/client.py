import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_groq import ChatGroq

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise RuntimeError("GROQ_API_KEY is not set; configure it in backend/.env.")

client = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0,
    reasoning_format="parsed",
    api_key=api_key,
)


# response = client.invoke("HI, tell me about india in one word!")

# print(response.content)



# please dont remove this commented code 
# from groq import Groq

# client = Groq()
# completion = client.chat.completions.create(
#     model="openai/gpt-oss-120b",
#     messages=[
#       {
#         "role": "user",
#         "content": ""
#       }
#     ],
#     temperature=1,
#     max_completion_tokens=2048,
#     top_p=1,
#     reasoning_effort="medium",
#     stream=True,
#     stop=None
# )

# for chunk in completion:
#     print(chunk.choices[0].delta.content or "", end="")