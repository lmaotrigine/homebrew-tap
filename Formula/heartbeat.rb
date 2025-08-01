# frozen_string_literal: true

# A service to show a live digital heartbeat (ping) on multiple devices 
class Heartbeat < Formula
  desc "A service to show a live digital heartbeat (ping) on multiple devices "
  homepage "https://github.com/lmaotrigine/heartbeat"
  version "0.1.1"
  license "MPL-2.0"

  if OS.mac?
    on_intel do
      url "https://github.com/lmaotrigine/heartbeat/releases/download/0.1.1/heartbeat-0.1.1-x86_64-apple-darwin.tar.xz"
      sha256 "f23655449a578b522f8385d657ad5acc61c2b7eaa56b1764f7e593176c20503e"
    end
    on_arm do
      url "https://github.com/lmaotrigine/heartbeat/releases/download/0.1.1/heartbeat-0.1.1-aarch64-apple-darwin.tar.xz"
      sha256 "21b0a579ad690cf3a45dc85b38a1e6308ff3e205b7faa76d539a6773f8ae6db2"
    end
  elsif OS.linux?
    on_intel do
      url "https://github.com/lmaotrigine/heartbeat/releases/download/0.1.1/heartbeat-0.1.1-x86_64-unknown-linux-musl.tar.xz"
      sha256 "791853c965e24e98f9420c143020719a757590c41bdfdaebdbb0d8293193262a"
    end
    on_arm do
      url "https://github.com/lmaotrigine/heartbeat/releases/download/0.1.1/heartbeat-0.1.1-aarch64-unknown-linux-musl.tar.xz"
      sha256 "1b1205d86b5196ced48599261d7b8b1a459bde205d3a03d359c80ec217d502be"
    end
  end

  def install
    bin.install "heartbeat"
  end
end
