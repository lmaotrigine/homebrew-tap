# frozen_string_literal: true

# Copy/paste anything over the network
class Klip < Formula
  desc "Copy/paste anything over the network"
  homepage "https://github.com/lmaotrigine/klip"
  version "0.2.0"
  license "MPL-2.0"

  if OS.mac?
    on_intel do
      url "https://github.com/lmaotrigine/klip/releases/download/0.2.0/klip-x86_64-apple-darwin.zip"
      sha256 "3c3aab887e403a8c6615776739cd313f750245209c43e13297abcd1adea2db28"
    end
    on_arm do
      url "https://github.com/lmaotrigine/klip/releases/download/0.2.0/klip-aarch64-apple-darwin.zip"
      sha256 "c1dcbd6490ca846e2380a7c886d9addd97c1dd0f49e7f15caa8d403bcb3bece6"
    end
  elsif OS.linux?
    on_intel do
      url "https://github.com/lmaotrigine/klip/releases/download/0.2.0/klip-x86_64-unknown-linux-musl.tar.xz"
      sha256 "9eb42d6fdae383b801664eecd9a14bdef644af7b85b6a2b640535e2c9284c12b"
    end
    on_arm do
      url "https://github.com/lmaotrigine/klip/releases/download/0.2.0/klip-aarch64-unknown-linux-musl.tar.xz"
      sha256 "670bde4c28978645dd47abd878eeea1c966aa83813b6ed322607e6444e29158b"
    end
  end

  def install
    bin.install "klip"
    man1.install "doc/klip.1"
    bash_completion.install "completions/klip.bash"
    zsh_completion.install "completions/_klip"
  end
end
