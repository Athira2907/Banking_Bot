from flask import Flask, request, jsonify
import openai

app = Flask(__name__)

# Set your OpenAI API key
openai.api_key = "your_openai_api_key"

# Simulated banking data
user_data = {
    "123456": {"balance": 1500, "transactions": ["-50: Grocery", "+200: Salary"]},
    "654321": {"balance": 3200, "transactions": ["-30: Coffee", "-100: Shopping"]},
}

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_id = data.get("user_id")
    user_message = data.get("message")
    
    if not user_id or user_id not in user_data:
        return jsonify({"response": "Invalid user ID."})
    
    # Define some banking-specific logic
    if "balance" in user_message.lower():
        balance = user_data[user_id]['balance']
        return jsonify({"response": f"Your balance is ${balance}."})
    
    elif "transactions" in user_message.lower():
        transactions = "\n".join(user_data[user_id]['transactions'])
        return jsonify({"response": f"Recent transactions:\n{transactions}"})
    
    else:
        # Use OpenAI API for other responses
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": user_message}]
        )
        return jsonify({"response": response['choices'][0]['message']['content']})

if __name__ == '__main__':
    app.run(debug=True)
