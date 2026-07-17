#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="${ROOT}/.tools"
QUARTO_VERSION="1.9.38"
TYPST_VERSION="0.15.0"
UV_VERSION="0.11.28"

mkdir -p "${TOOLS}"

if [[ ! -x "${TOOLS}/quarto/bin/quarto" ]]; then
  archive="${TOOLS}/quarto.tar.gz"
  curl --fail --location --retry 3 \
    "https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-amd64.tar.gz" \
    --output "${archive}"
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
  rm -rf "${TOOLS}/uv"
  mkdir -p "${TOOLS}/uv"
  tar -xzf "${archive}" --strip-components=1 -C "${TOOLS}/uv"
  rm -f "${archive}"
fi

"${TOOLS}/uv/uv" python install 3.12

