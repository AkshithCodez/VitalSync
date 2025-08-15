# VitalSync
Matrusri Hackathon
## ⚙️ Configuration

This project requires a Google Gemini API key to function. You must create a `.env` file to store this key securely.

1.  Obtain your free API key from [Google AI Studio](https://aistudio.google.com/).
2.  In the main project root folder (at the same level as the `project` and `venv` folders), create a new file named exactly **`.env`**.
3.  Add the following line to the `.env` file, replacing `YOUR_API_KEY_HERE` with the key you just copied:
    ```
    GEMINI_API_KEY="YOUR_API_KEY_HERE"
    ```

## 🚀 Running the Application

These instructions are for the Windows PowerShell terminal.

### First-Time Setup

Run this full sequence the very first time you set up the project.

1.  Navigate to the project folder:
    `cd path/to/your/VitalSync`

2.  Create the virtual environment:
    `python -m venv venv`

3.  Set the security policy for the session:
    `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process`

4.  Activate the virtual environment:
    `.\venv\Scripts\activate`

5.  Install all required packages:
    `pip install Flask Flask-SQLAlchemy Flask-Login python-dotenv google-generativeai`

6.  Initialize the database (this command only needs to be run once):
    `flask --app project init-db`

7.  Run the application:
    `flask --app project run`

### Subsequent Runs

For daily use, after the one-time setup is complete, you only need to run this shorter sequence from a new terminal:

1.  Navigate to the project folder:
    `cd path/to/your/VitalSync`

2.  Set the security policy for the session:
    `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process`

3.  Activate the virtual environment:
    `.\venv\Scripts\activate`

4.  Run the application:
    `flask --app project run`

The application will be available at `http://127.0.0.1:5000`.