from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, AuthKeyDuplicatedError, RPCError
import os

# Check if running in a local development environment
if not os.getenv('GITHUB_ACTIONS'):
    from dotenv import load_dotenv
    load_dotenv()

# Get values from environment variables
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
phone_number = os.getenv('PHONE_NUMBER')
pw2fa = os.getenv('PW2FA')
session_name = api_id + 'session_name'  # Ensure it matches the uploaded session file name

session_file = session_name + '.session'

# Create the client
client = TelegramClient(session_name, api_id, api_hash)

async def login():
    try:
        # Send verification code and start the login process
        print("Sending verification code to the specified phone number...", flush=True)
        await client.send_code_request(phone_number)

        # User inputs the received verification code
        code = input('Please enter the code you received(a): ')  
       
        # Use phone number and verification code to log in
        await client.sign_in(phone=phone_number, password=pw2fa, code=code)

    except SessionPasswordNeededError:
        # Handle two-factor authentication
        print("Two-factor authentication password is required", flush=True)
        await client.sign_in(password=pw2fa)

    except RPCError as e:
        # Capture RPC error and display detailed error message
        print(f"Failed to send verification request, error: {e}", flush=True)        

async def main():
    try:
        # Attempt to start the client
        print("Attempting to start the client...", flush=True)
        await client.connect()
    except AuthKeyDuplicatedError:
        # Capture AuthKeyDuplicatedError, delete the old session file and re-login
        print("Detected duplicate authorization key, deleting old session file and retrying login...", flush=True)
        await client.disconnect()  # Disconnect the client
        client.session.close()  # Ensure the session is closed
        if os.path.exists(session_file):
            os.remove(session_file)
            print("Session file deleted, restarting the client...", flush=True)

        # Reconnect after deleting the old session
        await client.connect()

    # Check if the user is already authorized
    if not await client.is_user_authorized():
        print("User is not authorized, starting the login process...", flush=True)
        await login()
    else:
        print("User is already authorized, no need to log in again", flush=True)

# Explicitly control client startup process instead of using `with client:`
if __name__ == '__main__':
    try:
        # client.start(phone=phone_number)
        client.loop.run_until_complete(main())
    except AuthKeyDuplicatedError:
        print("Handling AuthKeyDuplicatedError, deleting old session file...", flush=True)
        client.disconnect()  # Disconnect before deleting session file
        client.session.close()  # Ensure session file is released
        if os.path.exists(session_file):
            os.remove(session_file)
        print("Session file deleted, please rerun the program to verify...", flush=True)
    except Exception as e:
        print(f"An exception occurred: {e}", flush=True)
