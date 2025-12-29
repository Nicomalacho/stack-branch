class Gstack < Formula
  desc "CLI tool for managing stacked Git branches with automated rebasing"
  homepage "https://github.com/nicomalacho/stack-branch"
  version "0.2.0"
  license "MIT"

  on_macos do
    # ARM64 binary - Intel Macs can run via Rosetta 2
    url "https://github.com/nicomalacho/stack-branch/releases/download/v#{version}/gs-macos-arm64"
    sha256 "bf09715efbd8a6f646e4a6e3b363aae70125c69b28e98e69401fffda623e3f2b"

    def install
      bin.install "gs-macos-arm64" => "gs"
    end
  end

  on_linux do
    url "https://github.com/nicomalacho/stack-branch/releases/download/v#{version}/gs-linux-x86_64"
    sha256 "c6f55f1dc23359b99c3a34d206158fd9f5878b795ddb89fcf7a337da9156d345"

    def install
      bin.install "gs-linux-x86_64" => "gs"
    end
  end

  test do
    assert_match "Manage stacked Git branches", shell_output("#{bin}/gs --help")
  end
end
