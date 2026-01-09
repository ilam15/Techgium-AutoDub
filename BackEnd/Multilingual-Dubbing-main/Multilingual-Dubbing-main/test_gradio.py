import gradio as gr
def greet(name):
    return "Hello " + name + "!"
demo = gr.Interface(fn=greet, inputs="text", outputs="text")
try:
    demo.launch(server_name="127.0.0.1", server_port=7861)
except Exception as e:
    print(f"Error: {e}")
