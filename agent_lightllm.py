# agent_lightllm.py

import os
from pydantic import SecretStr

from openhands.sdk import LLM, Agent, Conversation, Tool
from openhands.tools.terminal import TerminalTool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool


def main():
    BASE_URL = os.getenv("LLM_BASE_URL")
    API_KEY = os.getenv("LLM_API_KEY") 
    MODEL = os.getenv("LLM_MODEL")

    llm = LLM(
        model=MODEL,
        base_url=BASE_URL,
        api_key=SecretStr(API_KEY),
        temperature=0.0,
        max_output_tokens=2048,
    )

    agent = Agent(
        llm=llm,
        tools=[
            Tool(name=TerminalTool.name),
            Tool(name=FileEditorTool.name),
            Tool(name=TaskTrackerTool.name),
        ],
    )

    conversation = Conversation(
        agent=agent,
        workspace=os.getcwd(),
        max_iteration_per_run=50,
    )

    conversation.send_message(
        "Создай файл test.txt и запиши туда строку: Hello from LightLLM agent"
    )

    conversation.run()

    print("Done ✅")


if __name__ == "__main__":
    main()