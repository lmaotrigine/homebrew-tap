# frozen_string_literal: true

# Copy/paste anything over the network
class Klip < Formula
  desc "Copy/paste anything over the network"
  homepage "https://github.com/lmaotrigine/klip"
  version "0.3.0"
  license "MPL-2.0"

  if OS.mac?
    on_intel do
      url "https://github.com/lmaotrigine/klip/releases/download/0.3.0/klip-x86_64-apple-darwin.zip"
      sha256 "14c66272390786280d5f832a458e9e42826b8fd2f13fdc40b07a7e5d3fff7215"
    end
    on_arm do
      url "https://github.com/lmaotrigine/klip/releases/download/0.3.0/klip-aarch64-apple-darwin.zip"
      sha256 "786019af71b4e091a7bda84c4b2e53aa16e727f370c379d1f2a5759572459e91"
    end
  elsif OS.linux?
    on_intel do
      url "https://github.com/lmaotrigine/klip/releases/download/0.3.0/klip-x86_64-unknown-linux-musl.tar.xz"
      sha256 "922f141a493a38f50abf240d58e385518493e88ca71638a6e998271ac462e03a"
    end
    on_arm do
      url "https://github.com/lmaotrigine/klip/releases/download/0.3.0/klip-aarch64-unknown-linux-musl.tar.xz"
      sha256 "dc15127cff888663f8cad3cbf5e257e5d993d94d34ce7cceb7c55099676b0f22"
    end
  end

  def install
    bin.install "klip"
    man1.install "doc/klip.1"
    bash_completion.install "completions/klip.bash"
    zsh_completion.install "completions/_klip"
  end
end
