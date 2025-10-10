#!/bin/bash

# Display Usage
usage() {
    echo "Usage: $0 [--model MODEL_NAME]"
    echo ""
    echo "Options:"
    echo "  --model MODEL_NAME    Specify which model to pull and run (default: llama2)"
    echo "  -h, --help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --model llama3"
    echo "  $0 --model mistral"
    echo "  $0 --model codellama"
}

MODEL=""
while [[ "$#" -gt 0 ]]; do
    case $1 in
    --model)
        MODEL="$2"
        shift 2
        ;;
    -h | --help)
        usage
        return
        ;;
    *)
        echo "Unknown Option: $1"
        echo "Use --help for usage information"
        return 1
        ;;
    esac
done

# Check if Ollama is installed
if ! command -v ollama >/dev/null 2>&1; then
    echo "Ollama not found. Installing..."
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "Ollama is already installed"
fi

# Pull the specified model
if [ -n $MODEL ]; then
    echo "Pulling model: $MODEL"
    ollama pull "$MODEL"
else
    echo "No model selected! Pulling tinyllama:latest and running it!"
    ollama pull tinyllama:latest
fi

echo "Running model: $MODEL"
echo "Starting interactive session..."
echo "Type '/bye' to exit"

ollama run "$MODEL"
