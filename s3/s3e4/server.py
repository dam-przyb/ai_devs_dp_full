import os
import csv
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

# Setup LangChain Model via OpenRouter
# Use the key provided in .env (either OPENROUTER_API_KEY or OPENROUTERKEY)
api_key = os.getenv("OPENROUTER_API_KEY", os.getenv("OPENROUTERKEY"))

llm = ChatOpenAI(
    model="openai/gpt-5.4-mini",
    openai_api_key=api_key,
    openai_api_base="https://openrouter.ai/api/v1",
)

# Load data into memory
items_map = {} # item_name -> item_code
code_to_name = {} # item_code -> item_name
base_dir = os.path.dirname(__file__)
with open(os.path.join(base_dir, "csvs", "items.csv"), "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    next(reader) # skip header
    for row in reader:
        if len(row) == 2:
            name, code = row
            items_map[name] = code
            code_to_name[code] = name

# We will supply the list of names to the LLM to find the exact match
all_item_names_str = "\n".join(items_map.keys())

cities_map = {} # city_code -> city_name
with open(os.path.join(base_dir, "csvs", "cities.csv"), "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    next(reader) # skip header
    for row in reader:
        if len(row) == 2:
            name, code = row
            cities_map[code] = name

connections = {} # item_code -> list of city_codes
with open(os.path.join(base_dir, "csvs", "connections.csv"), "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    next(reader) # skip header
    for row in reader:
        if len(row) == 2:
            item_code, city_code = row
            if item_code not in connections:
                connections[item_code] = []
            connections[item_code].append(city_code)

# Setup prompt template
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an assistant that maps a user's natural language request to an EXACT item name from a predefined list. "
               "The list contains electronic components. "
               "Return ONLY the exact name of the item from the list that best matches the user's request. "
               "Do not add any additional text, explanation, or formatting. If you cannot find a match, just return 'NOT FOUND'.\n\n"
               "Here is the list of available items:\n{item_list}"),
    ("human", "{query}")
])

chain = prompt | llm | StrOutputParser()

app = Flask(__name__)

@app.route("/api/find_item_cities", methods=["POST"])
def find_item_cities():
    data = request.get_json(force=True, silent=True)
    if not data or "params" not in data:
        return jsonify({"output": "Missing params"}), 400

    query = data["params"]
    print(f"Received query: {query}")

    # Use LLM to match query to exact item name
    try:
        matched_name = chain.invoke({
            "item_list": all_item_names_str,
            "query": query
        }).strip()
        print(f"LLM matched name: {matched_name}")
    except Exception as e:
        print(f"LLM error: {e}")
        return jsonify({"output": "LLM Error"}), 500

    if matched_name not in items_map:
        return jsonify({"output": "Item not found"}), 404

    item_code = items_map[matched_name]
    
    # Get cities for this item code
    city_codes = connections.get(item_code, [])
    city_names = [cities_map[code] for code in city_codes if code in cities_map]

    if not city_names:
        return jsonify({"output": "No cities found"}), 404

    # The response size limit is 500 bytes. A comma separated list will be small enough.
    response_text = ", ".join(city_names)
    print(f"Returning cities: {response_text}")

    return jsonify({"output": response_text})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
