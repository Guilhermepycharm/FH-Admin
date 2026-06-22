#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

function usage() {
  console.error("Usage: rpgsave_codec.js <decode|encode> <input> <output> <lz-string.js>");
  process.exit(2);
}

const [mode, input, output, library] = process.argv.slice(2);
if (!mode || !input || !output || !library || !["decode", "encode"].includes(mode)) usage();

const LZString = require(path.resolve(library));
const source = fs.readFileSync(input, "utf8");
const result = mode === "decode"
  ? LZString.decompressFromBase64(source)
  : LZString.compressToBase64(source);

if (result === null || result === "") {
  throw new Error(`${mode} produced empty output`);
}

fs.writeFileSync(output, result, "utf8");
console.log(`${mode}d ${input} -> ${output}`);
