# 🚀 Git Push Checklist - Environment Variables Secured

## ✅ Pre-Push Verification

Run these commands to verify everything is safe:

### 1. Check Token is Loaded
```bash
.\venv311\Scripts\python.exe -c "from dotenv import load_dotenv; import os; load_dotenv(); print('✅ OK' if os.getenv('HF_TOKEN') else '❌ FAIL')"
```
**Expected:** `✅ OK`

### 2. Verify .env is Ignored
```bash
git check-ignore .env
```
**Expected:** `.env`

### 3. Check What Will Be Committed
```bash
git status
```
**Should NOT see:** `.env` in the list

### 4. Search for Hardcoded Tokens
```bash
git grep -i "hf_hVIeb" || echo "✅ No hardcoded tokens found"
```
**Expected:** `✅ No hardcoded tokens found`

## 📝 Files to Commit

### ✅ Safe to Commit:
- `.env.example` - Template for team members
- `.gitignore` - Updated to exclude .env
- `requirements.txt` - Added python-dotenv
- `speaker_detection.py` - Loads from environment
- `START_WITH_DIARIZATION.bat` - No hardcoded token
- `ENV_SETUP.md` - Documentation
- All other code files

### ❌ Never Commit:
- `.env` - Contains your actual token
- `HF_TOKEN_CONFIGURED.md` - Contains token
- `START_WITH_DIARIZATION.bat` (if it still has hardcoded token)

## 🔐 Security Best Practices

### Before First Push:
```bash
# 1. Check for secrets
git diff --cached

# 2. Verify .env is ignored
git ls-files | grep ".env$" || echo "✅ .env not tracked"

# 3. Double-check .gitignore
cat .gitignore | grep "^\.env$"
```

### Safe Commit Commands:
```bash
# Add all files
git add .

# Review what will be committed
git status

# Commit with descriptive message
git commit -m "feat: Add environment variable support for secure token management

- Add .env file for local secrets (gitignored)
- Add .env.example template for team
- Update speaker_detection.py to load from environment
- Add python-dotenv dependency
- Remove hardcoded tokens from batch files"

# Push to remote
git push origin main
```

## 🎯 Quick Push (After Verification)

If all checks pass:
```bash
git add .
git commit -m "Add secure environment variable management"
git push
```

## ⚠️ If You Accidentally Committed .env

If you accidentally committed `.env` with your token:

### 1. Remove from Git (keep local file):
```bash
git rm --cached .env
git commit -m "Remove .env from version control"
git push
```

### 2. Rotate Your Token:
1. Go to https://huggingface.co/settings/tokens
2. Delete the old token
3. Create a new token
4. Update your local `.env` file

### 3. If Already Pushed to GitHub:
- **Immediately revoke the token** on Hugging Face
- Create a new token
- Consider the old token compromised

## 📋 Team Onboarding

When a teammate clones your repo, they should:

```bash
# 1. Copy the example
cp .env.example .env

# 2. Edit .env and add their token
# (Use notepad, VS Code, or any editor)

# 3. Verify it works
.\venv311\Scripts\python.exe -c "from dotenv import load_dotenv; import os; load_dotenv(); print('✅' if os.getenv('HF_TOKEN') else '❌')"
```

## 🔍 Final Verification

Before pushing, run this comprehensive check:

```bash
# Check .env is not tracked
git ls-files | grep "\.env$" && echo "⚠️ WARNING: .env is tracked!" || echo "✅ .env is safe"

# Check for hardcoded tokens in staged files
git diff --cached | grep -i "hf_hVIeb" && echo "⚠️ WARNING: Token found in staged files!" || echo "✅ No tokens in staged files"

# Verify .gitignore
grep "^\.env$" .gitignore && echo "✅ .env is in .gitignore" || echo "⚠️ WARNING: Add .env to .gitignore!"
```

---

## ✅ You're Ready to Push!

If all checks pass, your code is secure and ready for GitHub! 🎉

**Remember:** 
- `.env` stays local (never committed)
- `.env.example` goes to Git (safe template)
- Team members create their own `.env` from the example
