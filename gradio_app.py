from main import app, gemini_predict, driver, create_role, create_skill, create_tool
import gradio as gr

# Chat-style workflow function
def run_workflow(user_text, chat_history):
    if chat_history is None:
        chat_history = []

    inputs = {
        "user_text": user_text,
        "followup_question": user_text  # in chat, treat follow-up as same input
    }

    try:
        final_state = app.invoke(inputs)

        processed_text = final_state.get("processed_text", "")
        entities = final_state.get("entities", {})
        skills = final_state.get("expanded", {}).get("skills", [])
        tools = final_state.get("expanded", {}).get("tools", [])

        # Format skills (handle dicts with subtopics)
        skill_texts = []
        for s in skills:
            if isinstance(s, dict):
                name = s.get("name", "")
                subs = s.get("subtopics", [])
                if subs:
                    skill_texts.append(f"{name} → {', '.join(subs)}")
                else:
                    skill_texts.append(name)
            else:
                skill_texts.append(str(s))

        # Format tools (handle dicts or strings)
        tool_texts = []
        for t in tools:
            if isinstance(t, dict):
                tool_texts.append(t.get("name", str(t)))
            else:
                tool_texts.append(str(t))

        assistant_reply = (
            f"**Task:** {processed_text}\n\n"
            f"**Role:** {entities.get('role')}\n"
            f"**Type:** {entities.get('type')}\n"
            f"**Skills:** {', '.join(skill_texts)}\n"
            f"**Tools:** {', '.join(tool_texts)}"
        )

    except Exception as e:
        assistant_reply = f"Error running workflow: {e}"

    # Append user message and assistant reply to chat history
    chat_history.append((user_text, assistant_reply))
    return chat_history, chat_history

# Gradio Chat UI
with gr.Blocks() as demo:
    gr.Markdown("## Career Workflow Assistant (Chat)")
    chatbot = gr.Chatbot()
    user_input = gr.Textbox(placeholder="Type your career query here...")
    submit_btn = gr.Button("Send")

    submit_btn.click(run_workflow, inputs=[user_input, chatbot], outputs=[chatbot, chatbot])
    user_input.submit(run_workflow, inputs=[user_input, chatbot], outputs=[chatbot, chatbot])

# Launch Gradio
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", debug=True)




