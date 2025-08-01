# frozen_string_literal: true

# Copy/paste anything over the network
class Klip < Formula
  desc "Copy/paste anything over the network"
  homepage "https://github.com/lmaotrigine/klip"
  version "0.1.0"
  license "MPL-2.0"

  if OS.mac?
    on_intel do
      url "https://github.com/lmaotrigine/klip/releases/download/0.1.0/klip-x86_64-apple-darwin.full.zip"
      sha256 "80c4824aad513a2735eb4cb91b42950bf01fa613dcb2ee24b7012660a0523669"
    end
    on_arm do
      url "https://github.com/lmaotrigine/klip/releases/download/0.1.0/klip-aarch64-apple-darwin.full.zip"
      sha256 "63c8579bb31106dafd421060cdd6de3f1130a397dd8d2566e65bd75382701679"
    end
  elsif OS.linux?
    on_intel do
      url "https://github.com/lmaotrigine/klip/releases/download/0.1.0/klip-x86_64-unknown-linux-musl.full.tar.xz"
      sha256 "c976f3f33745057318bb6260614e43c70a6f8b8698b069fa0eaa863cc2dbb40e"
    end
    on_arm do
      url "https://github.com/lmaotrigine/klip/releases/download/0.1.0/klip-aarch64-unknown-linux-musl.full.tar.xz"
      sha256 "5c577d9000d22fc580dd9aed17837575e6ba05204317f4dbf25fcbc7d5fb5d83"
    end
  end

  def install
    bin.install "klip"
    man1.install "doc/klip.1"
    bash_completion.install "completions/klip.bash"
    zsh_completion.install "completions/_klip"
  end
end
