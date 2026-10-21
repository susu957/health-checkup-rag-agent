from app.agent import agent


def chat_with_agent():
    print("=== 智能助手已启动，输入 'exit' 退出 ===")
    history = []
    while True:
        user_input = input("\n你: ")
        if user_input.strip().lower() in ("exit", "quit"):
            break
        result = agent.invoke(
            {"messages": history + [{"role": "user", "content": user_input}]}
        )
        reply = result["messages"][-1].content
        print(f"助手: {reply}")
        history = result["messages"]


if __name__ == "__main__":
    chat_with_agent()