# Environment Variables Setup

This project uses environment variables to securely store sensitive information like API tokens.

## Quick Setup

### 1. Create your `.env` file

Copy the example file:
```bash
cp .env.example .env
```

Or on Windows:
```cmd
copy .env.example .env
```

### 2. Add your Hugging Face token

Edit `.env` and replace `your_huggingface_token_here` with your actual token:

```env
HF_TOKEN=hf_your_actual_token_here
```

### 3. Get your Hugging Face Token

1. Go to [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. Click "New token"
3. Name it "AutoDub" and select "Read" access
4. Copy the token (starts with `hf_...`)

### 4. Accept Model Terms

Visit these pages and click "Agree and access repository":
- [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
- [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)

## Important Security Notes

### ✅ DO:
- Keep your `.env` file private
- Add `.env` to `.gitignore` (already done)
- Use `.env.example` as a template for others
- Never commit your actual token to Git

### ❌ DON'T:
- Share your `.env` file
- Commit `.env` to version control
- Hardcode tokens in your code
- Share your HF token publicly

## How It Works

The application automatically loads environment variables from `.env` using `python-dotenv`:

```python
from dotenv import load_dotenv
load_dotenv()

# Now you can access the token
token = os.getenv("HF_TOKEN")
```

## Verifying Setup

After creating your `.env` file, start the backend:

```bash
START_WITH_DIARIZATION.bat
```

You should see:
```
Loading configuration from .env file...
Token will be loaded automatically from .env
✅ Pyannote speaker diarization loaded successfully.
```

## Troubleshooting

### "No HF token provided"
- Make sure `.env` file exists in the backend directory
- Check that `HF_TOKEN=` line has your actual token
- Verify no extra spaces around the `=` sign

### "Error loading pyannote"
- Ensure you accepted the model terms on Hugging Face
- Verify your token has "Read" access
- Check that the token is valid (not expired)

## For Team Members

When cloning this repository:

1. Copy `.env.example` to `.env`
2. Get your own HF token from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
3. Add it to your local `.env` file
4. Never commit your `.env` file

---

**Your `.env` file is already in `.gitignore` and will not be pushed to Git!** ✅
