class Gstack < Formula
  desc "CLI tool for managing stacked Git branches with automated rebasing"
  homepage "https://github.com/nicomalacho/stack-branch"
  version "0.1.0"
  license "MIT"

  on_macos do
    # ARM64 binary - Intel Macs can run via Rosetta 2
    url "https://github.com/nicomalacho/stack-branch/releases/download/v#{version}/gs-macos-arm64"
    sha256 "e7e83e950df1434ed56feb2956e81480793ce0f8e19dbbbfc4fdb6c226ec1376"

    def install
      bin.install "gs-macos-arm64" => "gs"
    end
  end

  on_linux do
    url "https://github.com/nicomalacho/stack-branch/releases/download/v#{version}/gs-linux-x86_64"
    sha256 "e03ffc88e2b9f9d85464d75ce4435fdceff08efca9c9ba695aafdead9a603d38"

    def install
      bin.install "gs-linux-x86_64" => "gs"
    end
  end

  test do
    assert_match "Manage stacked Git branches", shell_output("#{bin}/gs --help")
  end
end
