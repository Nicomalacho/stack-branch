#!/bin/bash
# Script to update the Homebrew formula with correct SHA256 values after a release
# Usage: ./update-formula.sh v0.1.0
# Requires: gh CLI (authenticated)

set -e

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 v0.1.0"
    exit 1
fi

# Remove 'v' prefix if present for the formula version
FORMULA_VERSION="${VERSION#v}"

REPO_OWNER="nicomalacho"
REPO_NAME="stack-branch"

echo "Downloading binaries using gh CLI..."

# Create temp directory
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

cd "$TMP_DIR"

# Download assets using gh (handles private repo auth)
echo "  Downloading gs-macos-arm64..."
gh release download "$VERSION" --repo "${REPO_OWNER}/${REPO_NAME}" --pattern "gs-macos-arm64"

echo "  Downloading gs-linux-x86_64..."
gh release download "$VERSION" --repo "${REPO_OWNER}/${REPO_NAME}" --pattern "gs-linux-x86_64"

# Calculate SHA256
SHA_MACOS_ARM64=$(shasum -a 256 gs-macos-arm64 | cut -d' ' -f1)
echo "    macOS ARM64 SHA256: ${SHA_MACOS_ARM64}"

SHA_LINUX=$(shasum -a 256 gs-linux-x86_64 | cut -d' ' -f1)
echo "    Linux SHA256: ${SHA_LINUX}"

cd - > /dev/null

echo ""
echo "Updating Formula/gstack.rb..."

# Update the formula file
FORMULA_FILE="Formula/gstack.rb"

# Update version
sed -i '' "s/version \".*\"/version \"${FORMULA_VERSION}\"/" "$FORMULA_FILE"

# Update SHA256 values (handles both placeholders and existing hashes)
sed -i '' "s/PLACEHOLDER_SHA256_MACOS_ARM64/${SHA_MACOS_ARM64}/" "$FORMULA_FILE"
sed -i '' "s/PLACEHOLDER_SHA256_LINUX_X86_64/${SHA_LINUX}/" "$FORMULA_FILE"

# Update existing SHA256 for macos section
sed -i '' "/on_macos/,/^  end/{s/sha256 \"[a-f0-9]\{64\}\"/sha256 \"${SHA_MACOS_ARM64}\"/;}" "$FORMULA_FILE"

# Update existing SHA256 for linux section
sed -i '' "/on_linux/,/^  end/{s/sha256 \"[a-f0-9]\{64\}\"/sha256 \"${SHA_LINUX}\"/;}" "$FORMULA_FILE"

echo ""
echo "Done! Formula updated for version ${VERSION}"
echo ""
echo "Next steps:"
echo "  1. Review: git diff Formula/gstack.rb"
echo "  2. Commit: git add Formula/gstack.rb && git commit -m 'Update to ${VERSION}' && git push"
