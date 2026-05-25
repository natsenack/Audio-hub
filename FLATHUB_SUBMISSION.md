# Submission Guide for Flathub

This guide describes how to prepare and submit Linux Audio Manager to Flathub.

## Prerequisites

- A GitHub account (to fork flathub/flathub)
- Flatpak tools installed: `flatpak`, `org.flatpak.Builder`
- Git configured with SSH keys (recommended)

## Local Testing

Before submitting, ensure the app builds and runs correctly locally.

### 1. Install Flathub Runtime and Builder

```bash
flatpak remote-add --if-not-exists --user flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install -y flathub org.gnome.Platform/x86_64/46
flatpak install -y flathub org.gnome.Sdk/x86_64/46
flatpak install -y flathub org.flatpak.Builder
```

### 2. Build Locally

```bash
bash build-flatpak.sh
```

Or manually:

```bash
flatpak run --command=flathub-build org.flatpak.Builder --install io.github.linux-audio-manager.json
```

### 3. Run the App

```bash
flatpak run io.github.linux-audio-manager
```

### 4. Run Linter

```bash
flatpak run --command=flatpak-builder-lint org.flatpak.Builder manifest io.github.linux-audio-manager.json
```

All warnings and errors must be resolved or justified before submission.

## Preparing for Submission

### Checklist

- [ ] Manifest builds locally without errors
- [ ] Linter passes (0 errors, acceptable warnings documented)
- [ ] App runs and functions correctly
- [ ] `.metainfo.xml` is valid and complete
- [ ] `.desktop` file is correctly formatted
- [ ] LICENSE file is included and matches declared license (GPL-3.0-or-later)
- [ ] Screenshots are added to `.metainfo.xml` (optional but recommended)
- [ ] GitHub repository is public and contains all source code
- [ ] README documents app purpose and usage

### GitHub Repository Setup

The app ID is `io.github.linux-audio-manager`, which implies:
- GitHub owner: `yourusername` → `io.github.yourusername`
- Repository: `linux-audio-manager`
- Full GitHub URL: `https://github.com/yourusername/linux-audio-manager`

**Before submission:** Update all references to your actual GitHub username and email.

### Update Files

Edit the following files with your information:

1. **pyproject.toml** - Update `Homepage` and `Repository` URLs
2. **data/io.github.linux-audio-manager.desktop** - Update email/urls
3. **data/io.github.linux-audio-manager.metainfo.xml** - Update urls
4. **debian/control** - Update maintainer email
5. **io.github.linux-audio-manager.json** - Verify runtime versions

## Submission Process

### Step 1: Fork Flathub Repository

```bash
gh repo fork --clone flathub/flathub --branch=new-pr
cd flathub
git checkout -b linux-audio-manager-submission new-pr
```

Or manually:
1. Go to https://github.com/flathub/flathub
2. Click "Fork" (uncheck "Copy master only")
3. Clone your fork and check out `new-pr` branch

### Step 2: Add Files to Submission Directory

```bash
mkdir -p flathub/io/github/linux-audio-manager
cp io.github.linux-audio-manager.json flathub/io/github/linux-audio-manager/
cp flathub.json flathub/io/github/linux-audio-manager/
```

### Step 3: Commit and Push

```bash
cd flathub
git add io/github/linux-audio-manager/
git commit -m "Add io.github.linux-audio-manager"
git push --set-upstream origin linux-audio-manager-submission
```

### Step 4: Open Pull Request

1. Go to your fork: https://github.com/yourusername/flathub
2. Click "New Pull Request"
3. Set base branch to `new-pr` (NOT `master`)
4. Set compare branch to your submission branch
5. Title: "Add io.github.linux-audio-manager"
6. In description, provide:
   - Brief app description
   - Link to source repository
   - Features overview
   - Any special notes

### Step 5: Address Review Comments

Reviewers may request:
- Manifest adjustments
- Permission changes
- Documentation updates
- Metadata corrections

**Important:** Do not close or update the PR base branch. Simply push changes to your submission branch.

### Step 6: Test Build (After Approval)

Once reviewers approve, comment on the PR:
```
bot, build
```

This triggers an official Flathub test build. If successful, the PR will be merged.

## Debian/Ubuntu Package Build

To build a `.deb` package for Debian-based systems:

```bash
python3 debian/deb-builder.py
```

Or manually:
```bash
dpkg-buildpackage -us -uc
```

The resulting `.deb` can be installed locally for testing before Flathub submission.

## Resources

- Flathub Documentation: https://docs.flathub.org/
- Manifest Reference: https://docs.flatpak.org/en/latest/manifests.html
- Flathub GitHub: https://github.com/flathub/flathub
- Flathub Matrix Chat: https://matrix.to/#/#flathub:matrix.org

## Support

- Issues or questions: Open an issue on GitHub or ask in Flathub Matrix
- Security concerns: Email admins@flathub.org
