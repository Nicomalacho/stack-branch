class Gstack < Formula
  desc "CLI tool for managing stacked Git branches with automated rebasing"
  homepage "https://github.com/nicomalacho/stack-branch"
  version "0.4.1"
  license "MIT"

  on_macos do
    # ARM64 binary - Intel Macs can run via Rosetta 2
    url "https://github.com/nicomalacho/stack-branch/releases/download/v#{version}/gs-macos-arm64"
    sha256 "d213b76994f4c6afd6d18de6e9cbfc4faa2e5949cc208492a1c0d071d69f63ea"

    def install
      bin.install "gs-macos-arm64" => "gs"
    end
  end

  on_linux do
    url "https://github.com/nicomalacho/stack-branch/releases/download/v#{version}/gs-linux-x86_64"
    sha256 "f03f41c67ce6ebe7fcdb775306ecda413aa24dac451f38b3c9576500b1d32bcd"

    def install
      bin.install "gs-linux-x86_64" => "gs"
    end
  end

  test do
    assert_match "Manage stacked Git branches", shell_output("#{bin}/gs --help")
  end
end
