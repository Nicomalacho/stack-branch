#!/bin/bash
# Script to update the Homebrew formula with correct SHA256 values after a release
# Usage: ./update-formula.sh v0.1.0

set -e

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 v0.1.0"
    exit 1
fi

# Remove 'v' prefix if present for the formula version
FORMULA_VERSION="${VERSION#v}"

REPO_OWNER="nicolasgaviria"
REPO_NAME="stack-branch"
BASE_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/download/${VERSION}"

echo "Downloading binaries and calculating SHA256..."

# Create temp directory
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

# Download and hash each binary
declare -A SHAS

for artifact in gs-macos-arm64 gs-macos-x86_64 gs-linux-x86_64; do
    echo "  Downloading $artifact..."
    curl -fsSL "${BASE_URL}/${artifact}" -o "${TMP_DIR}/${artifact}"
    SHAS[$artifact]=$(shasum -a 256 "${TMP_DIR}/${artifact}" | cut -d' ' -f1)
    echo "    SHA256: ${SHAS[$artifact]}"
done

echo ""
echo "Updating Formula/gs.rb..."

# Update the formula file
FORMULA_FILE="Formula/gs.rb"

# Update version
sed -i '' "s/version \".*\"/version \"${FORMULA_VERSION}\"/" "$FORMULA_FILE"

# Update SHA256 values
sed -i '' "s/PLACEHOLDER_SHA256_MACOS_ARM64/${SHAS[gs-macos-arm64]}/" "$FORMULA_FILE"
sed -i '' "s/PLACEHOLDER_SHA256_MACOS_X86_64/${SHAS[gs-macos-x86_64]}/" "$FORMULA_FILE"
sed -i '' "s/PLACEHOLDER_SHA256_LINUX_X86_64/${SHAS[gs-linux-x86_64]}/" "$FORMULA_FILE"

# Also update existing SHA256 values (for subsequent releases)
sed -i '' "s/sha256 \"[a-f0-9]\{64\}\"/sha256 \"${SHAS[gs-macos-arm64]}\"/1" "$FORMULA_FILE"

echo "Done! Formula updated for version ${VERSION}"
echo ""
echo "Next steps:"
echo "  1. Review the changes: git diff Formula/gs.rb"
echo "  2. Commit and push: git add Formula/gs.rb && git commit -m 'Update to ${VERSION}' && git push"
