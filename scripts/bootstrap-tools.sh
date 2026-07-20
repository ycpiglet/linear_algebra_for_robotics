#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="${ROOT}/.tools"
QUARTO_VERSION="1.9.38"
QUARTO_SHA256="ea8c897368791ad9f200010c087ea3111b2e556b12a960487dd4e216902aa102"
TYPST_VERSION="0.15.0"
TYPST_SHA256="59b207df01be2dab9f13e80f73d04d7ff8273ffd46b3dd1b9eef5c60f3eeabea"
UV_VERSION="0.11.28"
UV_SHA256="e490a6464492183c5d4534a5527fb4440f7f2bb2f228162ad7e4afe076dc0224"
ACTIONLINT_VERSION="1.7.12"
ACTIONLINT_SHA256="8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8"
SHELLCHECK_VERSION="0.11.0"
SHELLCHECK_SHA256="8c3be12b05d5c177a04c29e3c78ce89ac86f1595681cab149b65b97c4e227198"

mkdir -p "${TOOLS}"

if [[ ! -x "${TOOLS}/quarto/bin/quarto" ]]; then
  archive="${TOOLS}/quarto.tar.gz"
  curl --fail --location --retry 3 \
    "https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-amd64.tar.gz" \
    --output "${archive}"
  printf '%s  %s\n' "${QUARTO_SHA256}" "${archive}" | sha256sum --check --status
  rm -rf "${TOOLS}/quarto"
  mkdir -p "${TOOLS}/quarto"
  tar -xzf "${archive}" --strip-components=1 -C "${TOOLS}/quarto"
  rm -f "${archive}"
fi

if [[ ! -x "${TOOLS}/typst/typst" ]]; then
  archive="${TOOLS}/typst.tar.xz"
  curl --fail --location --retry 3 \
    "https://github.com/typst/typst/releases/download/v${TYPST_VERSION}/typst-x86_64-unknown-linux-musl.tar.xz" \
    --output "${archive}"
  printf '%s  %s\n' "${TYPST_SHA256}" "${archive}" | sha256sum --check --status
  rm -rf "${TOOLS}/typst"
  mkdir -p "${TOOLS}/typst"
  tar -xJf "${archive}" --strip-components=1 -C "${TOOLS}/typst"
  rm -f "${archive}"
fi

if [[ ! -x "${TOOLS}/uv/uv" ]]; then
  archive="${TOOLS}/uv.tar.gz"
  curl --fail --location --retry 3 \
    "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz" \
    --output "${archive}"
  printf '%s  %s\n' "${UV_SHA256}" "${archive}" | sha256sum --check --status
  rm -rf "${TOOLS}/uv"
  mkdir -p "${TOOLS}/uv"
  tar -xzf "${archive}" --strip-components=1 -C "${TOOLS}/uv"
  rm -f "${archive}"
fi

if [[ ! -x "${TOOLS}/actionlint/actionlint" ]]; then
  archive="${TOOLS}/actionlint.tar.gz"
  curl --fail --location --retry 3 \
    "https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/actionlint_${ACTIONLINT_VERSION}_linux_amd64.tar.gz" \
    --output "${archive}"
  printf '%s  %s\n' "${ACTIONLINT_SHA256}" "${archive}" | sha256sum --check --status
  rm -rf "${TOOLS}/actionlint"
  mkdir -p "${TOOLS}/actionlint"
  tar -xzf "${archive}" -C "${TOOLS}/actionlint" actionlint
  rm -f "${archive}"
fi

if [[ ! -x "${TOOLS}/shellcheck/shellcheck" ]]; then
  archive="${TOOLS}/shellcheck.tar.xz"
  curl --fail --location --retry 3 \
    "https://github.com/koalaman/shellcheck/releases/download/v${SHELLCHECK_VERSION}/shellcheck-v${SHELLCHECK_VERSION}.linux.x86_64.tar.xz" \
    --output "${archive}"
  printf '%s  %s\n' "${SHELLCHECK_SHA256}" "${archive}" | sha256sum --check --status
  rm -rf "${TOOLS}/shellcheck"
  mkdir -p "${TOOLS}/shellcheck"
  tar -xJf "${archive}" --strip-components=1 -C "${TOOLS}/shellcheck"
  rm -f "${archive}"
fi

"${TOOLS}/uv/uv" python install 3.12
