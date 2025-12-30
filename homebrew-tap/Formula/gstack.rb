class Gstack < Formula
  desc "CLI tool for managing stacked Git branches with automated rebasing"
  homepage "https://github.com/nicomalacho/stack-branch"
  version "0.3.0"
  license "MIT"

  on_macos do
    # ARM64 binary - Intel Macs can run via Rosetta 2
    url "https://github.com/nicomalacho/stack-branch/releases/download/v#{version}/gs-macos-arm64"
    sha256 "457330efabe2b954d8a1c1ae8f8c21ea0a007a0272ef5774a8e4081bc715dd0e"

    def install
      bin.install "gs-macos-arm64" => "gs"
    end
  end

  on_linux do
    url "https://github.com/nicomalacho/stack-branch/releases/download/v#{version}/gs-linux-x86_64"
    sha256 "0849f026f0ce8594215ab728c43cc879687b018fc6f88f9f07671a1f8deb9d1e"

    def install
      bin.install "gs-linux-x86_64" => "gs"
    end
  end

  test do
    assert_match "Manage stacked Git branches", shell_output("#{bin}/gs --help")
  end
end
