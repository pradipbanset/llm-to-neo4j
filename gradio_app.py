# from main import app, gemini_predict, driver, create_role, create_skill, create_tool
# import gradio as gr
# from main import app


# # def run_workflow(user_text, followup_question):
# #     inputs = {
# #         "user_text": user_text,
# #         "followup_question": followup_question
# #     }

# #     try:
# #         final_state = app.invoke(inputs)

# #         processed_text = final_state.get("processed_text", "")
# #         entities = final_state.get("entities", {})
# #         skills = final_state.get("expanded", {}).get("skills", [])
# #         tools = final_state.get("expanded", {}).get("tools", [])

# #         result = (
# #             f"Processed Text: {processed_text}\n\n"
# #             f"Entities: {entities}\n\n"
# #             f"Skills: {skills}\n\n"
# #             f"Tools: {tools}"
# #         )
# #         return result
# #     except Exception as e:
# #         return f"Error running workflow: {e}"


# def run_workflow(user_text, followup_question):
#     inputs = {
#         "user_text": user_text,
#         "followup_question": followup_question
#     }

#     try:
#         final_state_list = app.invoke(inputs)  # might be a list
#         final_state = final_state_list[-1] if isinstance(final_state_list, list) else final_state_list

#         processed_text = final_state.get("processed_text", "")
#         entities = final_state.get("entities", {})
#         skills = final_state.get("expanded", {}).get("skills", [])
#         tools = final_state.get("expanded", {}).get("tools", [])

#         result = (
#             f"Processed Text: {processed_text}\n\n"
#             f"Entities: {entities}\n\n"
#             f"Skills: {skills}\n\n"
#             f"Tools: {tools}"
#         )
#         return result
#     except Exception as e:
#         return f"Error running workflow: {e}"



# # Gradio UI
# with gr.Blocks() as demo:
#     gr.Markdown("## Career Workflow Assistant")
#     user_input = gr.Textbox(label="Career Query", placeholder="E.g., I want to be a data engineer")
#     followup_input = gr.Textbox(label="Follow-up Question", placeholder="E.g., What skills are required?")
#     output_box = gr.Textbox(label="Workflow Result", lines=15)

#     submit_btn = gr.Button("Submit")
#     submit_btn.click(run_workflow, inputs=[user_input, followup_input], outputs=output_box)

# # Launch Gradio
# if __name__ == "__main__":
#     demo.launch(server_name="0.0.0.0", debug=True)




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
