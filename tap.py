#!/usr/bin/env python3

from __future__ import annotations

import concurrent.futures as cf
import json
import logging
import os
import re
import subprocess
import sys
import time
import tomllib
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

TYPE_CHECKING = False
if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any

_log = logging.getLogger('tap')

USER_AGENT = 'github.com/lmaotrigine/homebrew-tap@1.0'

FORMULA_TEMPLATE = """\
# frozen_string_literal: true

# {desc}
class {cname} < Formula
  desc "{desc}"
  homepage "{homepage}"
  version "{version}"
  license "{license}"
{depsfmt}
  if OS.mac?
    on_intel do
      url "{mac_x86_64_url}"
      sha256 "{mac_x86_64_sha256}"
    end
    on_arm do
      url "{mac_aarch64_url}"
      sha256 "{mac_aarch64_sha256}"
    end
  elsif OS.linux?
    on_intel do
      url "{linux_x86_64_url}"
      sha256 "{linux_x86_64_sha256}"
    end
    on_arm do
      url "{linux_aarch64_url}"
      sha256 "{linux_aarch64_sha256}"
    end
  end

  def install{binsfmt}{mansfmt}{completionsfmt}
  end
end
"""


def to_pascal_case(s: str) -> str:
    return ''.join(word.capitalize() for word in re.split(r'[\W_]+', s) if word)


def red(s: object) -> str:
    return f'\033[91m{s}\033[0m'


def green(s: object) -> str:
    return f'\033[92m{s}\033[0m'


def yellow(s: object) -> str:
    return f'\033[93m{s}\033[0m'


def cyan(s: object) -> str:
    return f'\033[96m{s}\033[0m'


def bright_green(s: object) -> str:
    return f'\033[92;1m{s}\033[0m'


def bright_yellow(s: object) -> str:
    return f'\033[93;1m{s}\033[0m'


def bright_blue(s: object) -> str:
    return f'\033[94;1m{s}\033[0m'


class GithubClient:
    __slots__ = ('server_url', 'token')

    def __init__(self, server_url: str, token: str) -> None:
        self.server_url = server_url
        self.token = token

    def get_latest_release_version(self, owner: str, repo: str) -> str | None:
        url = f'{self.server_url}/repos/{owner}/{repo}/releases/latest'
        _log.info("Fetching latest release for repository '%s/%s' from %r", owner, repo, url)
        start = time.monotonic()
        req = Request(
            url,
            headers={
                'User-Agent': USER_AGENT,
                'Accept': 'application/vnd.github.v3+json',
                'Authorization': f'token {self.token}',
                'X-GitHub-Api-Version': '2022-11-28',
            },
        )
        with urlopen(req) as resp:
            status = resp.status
            elapsed = time.monotonic() - start
            _log.info('Request completed in %dms with status %d', elapsed * 1000, status)
            if status != 200:
                body = resp.read().decode('utf-8')
                _log.debug('Error response: %s', body)
                msg = f'Failed to get latest release: HTTP status {status}'
                raise RuntimeError(msg)
            body = resp.read().decode('utf-8')
        _log.debug('Response body size: %d bytes', len(body))
        release = json.loads(body)
        try:
            tag_name = release['tag_name']
        except KeyError:
            _log.info('Release found but no tag_name present')
            return None
        return tag_name.lstrip('v')


def run_command(command: str, args: Iterable[str], env: dict[str, str] | None = None) -> None:
    _log.debug('🚀 Running command: %s %s', cyan(command), cyan(' '.join(args)))
    start_time = time.monotonic()
    status = subprocess.call([command, *args], stdin=subprocess.DEVNULL, env=env)
    duration = time.monotonic() - start_time
    status_icon = '✅' if status == 0 else red('❌')
    status_msg = 'executed successfully' if status == 0 else 'failed'
    style = green if status == 0 else red
    fmt_args = (
        "%s Command '%s' with args '%s' %s in %sms with status code %s",
        status_icon,
        cyan(command),
        cyan(' '.join(args)),
        style(status_msg),
        cyan(round(duration * 1000, 2)),
        yellow(status),
    )
    if status == 0:
        _log.debug(*fmt_args)
    else:
        _log.error(*fmt_args)
    if status != 0:
        _log.error("That command had to not fail. We're going to bail now. Toodles!")
        sys.exit(status)


def get_stdout(command: str, args: Iterable[str], env: dict[str, str] | None = None) -> str:
    _log.debug('🚀 Running command: %s %s', cyan(command), cyan(' '.join(args)))
    proc = subprocess.Popen(
        [command, *args], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
    )
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        _log.error('Command failed with status code %d', proc.returncode)
        sys.stderr.write(f'STDOUT: {stdout.decode("utf-8")}\n')
        sys.stderr.write(f'STDERR: {stderr.decode("utf-8")}\n')
        sys.exit(proc.returncode)
    return stdout.decode('utf-8')


def get_trimmed_stdout(command: str, args: Iterable[str], env: dict[str, str] | None = None) -> str:
    return get_stdout(command, args, env).strip()


class Archive:
    __slots__ = ('sha256', 'url')

    def __init__(self, url: str, sha256: str) -> None:
        self.url: str = url
        self.sha256: str = sha256


class Archives:
    __slots__ = ('linux_aarch64', 'linux_x86_64', 'mac_aarch64', 'mac_x86_64')

    def __init__(
        self,
        *,
        mac_aarch64: Archive,
        mac_x86_64: Archive,
        linux_aarch64: Archive,
        linux_x86_64: Archive,
    ) -> None:
        self.mac_aarch64: Archive = mac_aarch64
        self.mac_x86_64: Archive = mac_x86_64
        self.linux_aarch64: Archive = linux_aarch64
        self.linux_x86_64: Archive = linux_x86_64


class Man:
    __slots__ = ('path', 'section')

    def __init__(self, section: int, path: str) -> None:
        self.section: int = section
        self.path: str = path

    @classmethod
    def parse(cls, s: str) -> Man:
        return cls(int(s[-1]), s)

    def format(self) -> str:
        return f'man{self.section}.install "{self.path}"'


class Completion:
    __slots__ = ('path', 'shell')

    def __init__(self, shell: str, path: str) -> None:
        self.shell: str = shell
        self.path: str = path

    @classmethod
    def parse(cls, s: str) -> Completion:
        _, ext = os.path.splitext(s)  # noqa: PTH122 # just string parsing
        # zsh is _{prog}
        shell = 'zsh' if not ext else ext.lstrip('.')
        return cls(shell, s)

    def format(self) -> str:
        return f'{self.shell}_completion.install "{self.path}"'


class Formula:
    __slots__ = (
        'archive_fmt',
        'bins',
        'completions',
        'darwin_ext',
        'deps',
        'desc',
        'homepage',
        'license',
        'linux_ext',
        'mans',
        'repo',
    )

    def __init__(
        self,
        *,
        repo: str,
        homepage: str,
        desc: str,
        license: str,  # noqa: A002  # why?
        bins: list[str],
        mans: list[Man],
        deps: list[str],
        completions: list[Completion],
        archive_fmt: str | None = None,
        linux_ext: str = 'tar.xz',
        darwin_ext: str = 'tar.xz',
    ) -> None:
        self.repo: str = repo
        self.homepage: str = homepage
        self.desc: str = desc
        self.license: str = license
        self.bins: list[str] = bins
        self.mans: list[Man] = mans
        self.deps: list[str] = deps
        self.completions: list[Completion] = completions
        self.archive_fmt: str = archive_fmt or '{name}-{arch}.{ext}'
        self.linux_ext: str = linux_ext
        self.darwin_ext: str = darwin_ext

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Formula:
        return cls(
            repo=d['repo'],
            homepage=d['homepage'],
            desc=d['desc'],
            license=d['license'],
            bins=d['bins'],
            mans=[Man.parse(m) for m in d.get('mans', [])],
            deps=d.get('deps', []),
            completions=[Completion.parse(c) for c in d.get('completions', [])],
            linux_ext=d.get('linux_ext', 'tar.xz'),
            darwin_ext=d.get('darwin_ext', 'tar.xz'),
            archive_fmt=d.get('archive_fmt', '{name}-{arch}.{ext}'),
        )

    @property
    def org(self) -> str:
        return self.repo.split('/')[0]

    @property
    def name(self) -> str:
        return self.repo.split('/')[1]

    @property
    def disk_path(self) -> Path:
        return Path(__file__).with_name('Formula').joinpath(f'{self.name}.rb')

    def github_version(self, _conf: TapConfig, github_token: str) -> str | None:
        gh_client = GithubClient('https://api.github.com', github_token)
        return gh_client.get_latest_release_version(self.org, self.name)

    def formula_version(self) -> str | None:
        disk_path = self.disk_path
        if not disk_path.exists():
            return None
        content = disk_path.read_text(encoding='utf-8')
        version_line = next(line for line in content.splitlines() if line.strip().startswith('version'))
        return version_line.split('"')[1]


class TapConfig:
    def __init__(self, formulas: list[Formula]) -> None:
        self.formulas: list[Formula] = formulas

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TapConfig:
        return cls([Formula.from_dict(f) for f in d['formula']])


class VersionUpToDate(Exception): ...


class HomebrewContext:
    __slots__ = ('dry_run', 'formula', 'new_version')

    def __init__(self, *, formula: Formula, github_version: str, dry_run: bool) -> None:
        formula_version = formula.formula_version()
        if formula_version == github_version:
            _log.info(
                'Formula version %s is already up to date with GitHub version %s',
                bright_green(formula_version),
                bright_green(github_version),
            )
            raise VersionUpToDate
        self.dry_run: bool = dry_run
        self.formula: Formula = formula
        self.new_version: str = github_version

    def fetch_and_hash(self, url: str) -> str:
        _log.info('Fetching archive from %s...', cyan(url))
        if self.dry_run:
            _log.info('Dry run: Would fetch %s', bright_yellow('archive'))
            return sha256(url.encode('utf-8')).hexdigest()
        with urlopen(url) as resp:
            if resp.status != 200:
                err_text = resp.read().decude('utf-8')
                _log.error('Failed to fetch archive: HTTP status %s, Response: %s', red(resp.status), red(err_text))
                msg = f'Failed to fetch archive: HTTP status {resp.status}'
                raise RuntimeError(msg)
            body = resp.read()
        count = len(body)
        sha = sha256(body).hexdigest()
        _log.info('Archive fetched (%s bytes) and SHA256 %s', green(count), green('computed'))
        return sha

    def get_archive(self, url: str) -> Archive:
        return Archive(url=url, sha256=self.fetch_and_hash(url))

    def package_artifact_url(self, arch: str) -> str:
        ext = self.formula.darwin_ext if arch.endswith('darwin') else self.formula.linux_ext
        fmt = self.formula.archive_fmt.format(name=self.formula.name, version=self.new_version, arch=arch, ext=ext)
        url = f'https://github.com/{self.formula.org}/{self.formula.name}/releases/download/{self.new_version}/{fmt}'
        _log.info('URL for releases: %s', cyan(url))
        return url

    def update_formula(self) -> None:
        _log.info('Updating Homebrew %s...', bright_yellow('formula'))
        mac_aarch64_url = self.package_artifact_url('aarch64-apple-darwin')
        mac_x86_64_url = self.package_artifact_url('x86_64-apple-darwin')
        linux_aarch64_url = self.package_artifact_url('aarch64-unknown-linux-musl')
        linux_x86_64_url = self.package_artifact_url('x86_64-unknown-linux-musl')
        with cf.ThreadPoolExecutor(max_workers=4) as executor:
            mac_aarch64_future = executor.submit(self.get_archive, mac_aarch64_url)
            mac_x86_64_future = executor.submit(self.get_archive, mac_x86_64_url)
            linux_aarch64_future = executor.submit(self.get_archive, linux_aarch64_url)
            linux_x86_64_future = executor.submit(self.get_archive, linux_x86_64_url)
            mac_aarch64 = mac_aarch64_future.result()
            mac_x86_64 = mac_x86_64_future.result()
            linux_aarch64 = linux_aarch64_future.result()
            linux_x86_64 = linux_x86_64_future.result()
        archives = Archives(
            mac_aarch64=mac_aarch64,
            mac_x86_64=mac_x86_64,
            linux_aarch64=linux_aarch64,
            linux_x86_64=linux_x86_64,
        )
        formula = self.generate_homebrew_formula(archives)
        formula_path = self.formula.disk_path
        if self.dry_run:
            _log.info('Dry run: Would write formula to %s', cyan(formula_path))
            _log.info('Formula content:\n%s', formula)
        else:
            formula_path.parent.mkdir(parents=True, exist_ok=True)
            formula_path.write_text(formula, encoding='utf-8')
            _log.info('Homebrew formula written to %s', bright_green(formula_path))

    def generate_homebrew_formula(self, archives: Archives) -> str:
        def format_dep(dep: str) -> str:
            parts = dep.split('#')
            if len(parts) == 1:
                name = parts[0]
                kw = None
            elif len(parts) == 2:
                name, kw = parts
            else:
                msg = 'Invalid dependency syntax. Use "name" or "name#keyword" where keyword is "optional" or "recommended"'
                raise ValueError(msg)
            if kw is None:
                return f'"{name}"'
            if kw == 'optional':
                return f'"{name}" => :optional'
            if kw == 'recommended':
                return f'"{name}" => :recommended'
            msg = f"Unknown dependency keyword {kw!r}. Use 'optional' or 'recommended'"
            raise ValueError(msg)

        depsfmt = '\n'.join(f'  depends_on {format_dep(dep)}' for dep in self.formula.deps)
        if depsfmt:
            depsfmt = f'\n{depsfmt}'
        binsfmt = '\n'.join(f'    bin.install "{b}"' for b in self.formula.bins)
        if binsfmt:
            binsfmt = f'\n{binsfmt}'
        mansfmt = '\n'.join(f'    {m.format()}' for m in self.formula.mans)
        if mansfmt:
            mansfmt = f'\n{mansfmt}'
        completionsfmt = '\n'.join(f'    {c.format()}' for c in self.formula.completions)
        if completionsfmt:
            completionsfmt = f'\n{completionsfmt}'
        return FORMULA_TEMPLATE.format(
            cname=to_pascal_case(self.formula.name),
            desc=self.formula.desc,
            homepage=self.formula.homepage,
            version=self.new_version,
            license=self.formula.license,
            depsfmt=depsfmt,
            mac_x86_64_url=archives.mac_x86_64.url,
            mac_x86_64_sha256=archives.mac_x86_64.sha256,
            mac_aarch64_url=archives.mac_aarch64.url,
            mac_aarch64_sha256=archives.mac_aarch64.sha256,
            linux_x86_64_url=archives.linux_x86_64.url,
            linux_x86_64_sha256=archives.linux_x86_64.sha256,
            linux_aarch64_url=archives.linux_aarch64.url,
            linux_aarch64_sha256=archives.linux_aarch64.sha256,
            binsfmt=binsfmt,
            mansfmt=mansfmt,
            completionsfmt=completionsfmt,
        )


def load_tap_config() -> TapConfig:
    config_path = Path(__file__).with_name('.tap.toml').resolve(strict=True)
    config_str = config_path.read_text(encoding='utf-8')
    config = tomllib.loads(config_str)
    return TapConfig.from_dict(config)


def update_tap() -> None:
    try:
        os.environ['DRY_RUN']
    except KeyError:
        dry_run = False
    else:
        dry_run = True
    if dry_run:
        _log.info('Dry run %s', bright_yellow('enabled'))
    github_token = os.environ['GITHUB_TOKEN']
    _log.info('Loading tap %s...', cyan('configuration'))
    config = load_tap_config()
    _log.info('Tap configuration loaded %s', green('successfully'))
    _log.info('Processing %s...', bright_yellow('formulas'))
    bumped: list[tuple[str, str]] = []
    for i, formula in enumerate(config.formulas, 1):
        _log.info('Processing formula %s of %s: %s', cyan(i), cyan(len(config.formulas)), cyan(formula.name))
        _log.info('Fetching GitHub %s...', cyan('version'))
        github_version = formula.github_version(config, github_token)
        if github_version is None:
            _log.info('No version found for %s, skipping', cyan(formula.name))
            continue
        _log.info('GitHub version: %s', green(github_version))
        try:
            ctx = HomebrewContext(formula=formula, github_version=github_version, dry_run=dry_run)
        except VersionUpToDate:
            _log.info('No update needed for %s', bright_blue(formula.name))
        else:
            _log.info('Updating formula for %s...', bright_yellow(formula.name))
            ctx.update_formula()
            _log.info('Formula update completed for %s', bright_green(formula.name))
            bumped.append((formula.name, github_version))
    _log.info('All formulas %s', bright_green('processed'))
    if not bumped:
        _log.info('No formulas were bumped')
    else:
        commit_msg = ', '.join(f'{name} to {version}' for name, version in bumped)
        full_msg = f'Bump formulas: {commit_msg}'
        _log.info('Committing changes...')
        if dry_run:
            _log.info('Dry run: Would commit changes with message: %s', cyan(full_msg))
        else:
            run_command('git', ['add', '.'])
            run_command(
                'git',
                ['commit', '-m', full_msg],
                {
                    'GIT_AUTHOR_NAME': 'homebrew-tap',
                    'GIT_AUTHOR_EMAIL': 'isis@5ht2.me',
                    'GIT_COMMITTER_NAME': 'homebrew-tap',
                    'GIT_COMMITTER_EMAIL': 'isis@5ht2.me',
                    'TZ': 'UTC',
                },
            )
            _log.info('Changes committed successfully')
        _log.info('Formulas bumped:')
        for name, version in bumped:
            _log.info('  %s to version %s', cyan(name), green(version))
        _log.info('Pushing changes...')
        remote = get_trimmed_stdout('git', ['remote', '-v'])
        # make ssh url into https
        remote_url = (
            next(line for line in remote.splitlines() if '(push)' in line)
            .split()[1]
            .replace('git@github.com:', 'https://github.com/')
        )
        org_repo = '/'.join(remote_url.removeprefix('https://').removesuffix('.git').split('/')[1:3])
        _log.info('Remote URL: %s', cyan(remote_url))
        _log.info('Organization/Repo: %s', cyan(org_repo))
        # this is a bit of a clusterfuck
        # urlparse's result doesn't allow you to set username and password
        # we also can't rely on it being unset initially because CI has remotes with credentials sometimes
        # so, we naively parse the netloc, and then unparse it to get a string back
        parsed = urlparse(remote_url)
        domain = parsed.netloc.split('@')[-1]
        if dry_run:
            _log.info('Dry run: Would push changes to remote repository')
            _log.info('Push command that would be executed:')
            domain = f'token:REDACTED@{domain}'
            unparsed = (parsed[0], domain, parsed[2], parsed[3], parsed[4], parsed[5])
            _log.info('git push %s HEAD:mistress', cyan(urlunparse(unparsed)))
        else:
            domain = f'token:{github_token}@{domain}'
            unparsed = (parsed[0], domain, parsed[2], parsed[3], parsed[4], parsed[5])
            run_command('git', ['push', urlunparse(unparsed), 'HEAD:mistress'])
            _log.info('Changes pushed successfully')


def main() -> None:
    # having levelname would be nice for non-info i guess, but oh well
    logging.basicConfig(datefmt=None, level=logging.INFO, format='%(message)s')
    update_tap()


if __name__ == '__main__':
    main()
