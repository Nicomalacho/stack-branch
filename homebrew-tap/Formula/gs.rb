class Gs < Formula
  desc "CLI tool for managing stacked Git branches with automated rebasing"
  homepage "https://github.com/nicolasgaviria/stack-branch"
  version "0.1.0"
  license "MIT"

  on_macos do
    on_arm do
      url "https://github.com/nicolasgaviria/stack-branch/releases/download/v#{version}/gs-macos-arm64"
      sha256 "PLACEHOLDER_SHA256_MACOS_ARM64"

      def install
        bin.install "gs-macos-arm64" => "gs"
      end
    end

    on_intel do
      url "https://github.com/nicolasgaviria/stack-branch/releases/download/v#{version}/gs-macos-x86_64"
      sha256 "PLACEHOLDER_SHA256_MACOS_X86_64"

      def install
        bin.install "gs-macos-x86_64" => "gs"
      end
    end
  end

  on_linux do
    on_intel do
      url "https://github.com/nicolasgaviria/stack-branch/releases/download/v#{version}/gs-linux-x86_64"
      sha256 "PLACEHOLDER_SHA256_LINUX_X86_64"

      def install
        bin.install "gs-linux-x86_64" => "gs"
      end
    end
  end

  test do
    assert_match "Manage stacked Git branches", shell_output("#{bin}/gs --help")
  end
end
