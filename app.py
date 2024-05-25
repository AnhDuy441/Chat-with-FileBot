from flask import Flask, request, render_template, redirect, url_for
from transformers import pipeline
import fitz
import docx
import os
import json

app = Flask(__name__)

qa_model = None
context = ""
chat_history = []
conversations_dir = 'conversations'  # Directory to save conversations

def read_pdf(file_path):
    doc = fitz.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def read_docx(file_path):
    doc = docx.Document(file_path)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

def read_txt(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        text = file.read()
    return text

def process_text(text):
    lines = text.split('\n')
    processed_text = []
    for line in lines:
        if line.strip():  # Check if the line is not empty
            # If processed_text is not empty and the last character of the last line is not a period
            if processed_text and processed_text[-1] and processed_text[-1][-1] != '.':
                processed_text[-1] += line
            else:
                processed_text.append(line)
    return '\n'.join(processed_text)

def create_qa_model(text):
    qa_pipeline = pipeline("question-answering", model='distilbert-base-cased-distilled-squad')
    processed_text = process_text(text)
    context = processed_text
    return qa_pipeline, context

def save_conversation(conversation_id, filename, chat_history, context):
    conversation_path = os.path.join(conversations_dir, conversation_id)
    if not os.path.exists(conversation_path):
        os.makedirs(conversation_path)
    with open(os.path.join(conversation_path, 'filename.txt'), 'w', encoding='utf-8') as f:
        f.write(filename)
    with open(os.path.join(conversation_path, 'chat_history.json'), 'w', encoding='utf-8') as f:
        json.dump(chat_history, f)
    with open(os.path.join(conversation_path, 'context.txt'), 'w', encoding='utf-8') as f:
        f.write(context)

def load_conversations():
    conversations = []
    if os.path.exists(conversations_dir):
        for conversation_id in os.listdir(conversations_dir):
            conversation_path = os.path.join(conversations_dir, conversation_id)
            if os.path.isdir(conversation_path):
                with open(os.path.join(conversation_path, 'filename.txt'), 'r', encoding='utf-8') as f:
                    filename = f.read().strip()
                with open(os.path.join(conversation_path, 'chat_history.json'), 'r', encoding='utf-8') as f:
                    chat_history = json.load(f)
                with open(os.path.join(conversation_path, 'context.txt'), 'r', encoding='utf-8') as f:
                    context = f.read().strip()
                conversations.append((conversation_id, filename, chat_history, context))
    return conversations

@app.route("/", methods=["GET", "POST"])
def index():
    global qa_model, context, chat_history, previous_conversations
    chat_history = []  # Reset chat history when a new file is uploaded
    if request.method == "POST":
        file = request.files["file"]
        if file:
            file_path = os.path.join("uploads", file.filename)
            file.save(file_path)
            if file.filename.endswith(".pdf"):
                text = read_pdf(file_path)
            elif file.filename.endswith(".docx"):
                text = read_docx(file_path)
            elif file.filename.endswith(".txt"):
                text = read_txt(file_path)
            else:
                return "Unsupported file type"
            qa_model, context = create_qa_model(text)
            conversation_id = str(len(previous_conversations))
            previous_conversations.append((conversation_id, file.filename, chat_history, context))  # Save the filename and conversation before resetting
            save_conversation(conversation_id, file.filename, chat_history, context)
            chat_history = []  # Reset chat history for new conversation
            print("Context:", context)
            return redirect(url_for("chat", conversation_id=conversation_id))
    previous_conversations = load_conversations()  # Load previous conversations on startup
    return render_template("index.html", previous_conversations=previous_conversations)

@app.route("/chat", methods=["GET", "POST"])
def chat():
    global qa_model, context, chat_history, previous_conversations
    conversation_id = request.args.get("conversation_id")
    if conversation_id:
        conversation = next((conv for conv in previous_conversations if conv[0] == conversation_id), None)
        if conversation:
            _, _, chat_history, context = conversation
            qa_model, _ = create_qa_model(context)
    if request.method == "POST":
        user_question = request.form["message"]
        response = qa_model(question=user_question, context=context)
        answer = response['answer']
        chat_history.append({
            "user_input": user_question,
            "bot_response": answer
        })
        save_conversation(conversation_id, conversation[1], chat_history, context)
        return render_template("chat.html", chat_history=chat_history, context=context, previous_conversations=previous_conversations, enumerate=enumerate)
    return render_template("chat.html", chat_history=chat_history, context=context, previous_conversations=previous_conversations, enumerate=enumerate)

if __name__ == "__main__":
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    if not os.path.exists(conversations_dir):
        os.makedirs(conversations_dir)
    previous_conversations = load_conversations()
    app.run(debug=True)
