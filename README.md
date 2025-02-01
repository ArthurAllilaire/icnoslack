# Project Setup

To set up the project run the following commands:

```sh

chmod +x setup.sh
./setup.sh
pip install -r requirements.txt
```

# Anthropic:
Set up the Anthropic API key in the environment variable `ANTHROPIC_API_KEY`:

```sh
pip install -r requirements.txt # Install the required packages
export ANTHROPIC_API_KEY=<API_KEY>
```
## Running the Flask Web App

To run the Flask web app, make sure you have set up the virtual environment and installed Flask. Then, run the following command:

```sh
source venv/bin/activate
python app.py
```

