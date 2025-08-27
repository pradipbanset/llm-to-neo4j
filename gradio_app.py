from main import app, gemini_predict, driver, create_role, create_skill, create_tool
from main import app
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
        # app.invoke may return a list, so handle that
        final_state_list = app.invoke(inputs)
        final_state = final_state_list[-1] if isinstance(final_state_list, list) else final_state_list

        processed_text = final_state.get("processed_text", "")
        entities = final_state.get("entities", {})
        skills = final_state.get("expanded", {}).get("skills", [])
        tools = final_state.get("expanded", {}).get("tools", [])

        assistant_reply = (
            f"**Task:** {processed_text}\n\n"
            f"**Role:** {entities.get('role')}\n"
            f"**Type:** {entities.get('type')}\n"
            f"**Skills:** {', '.join(skills)}\n"
            f"**Tools:** {', '.join(tools)}"
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

    # On click or enter, run the workflow
    submit_btn.click(run_workflow, inputs=[user_input, chatbot], outputs=[chatbot, chatbot])
    user_input.submit(run_workflow, inputs=[user_input, chatbot], outputs=[chatbot, chatbot])

# Launch Gradio
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", debug=True)
