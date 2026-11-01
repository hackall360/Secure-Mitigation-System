// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · model/parse-binary.js — real topology parsed from a compiled binary: ELF headers, sections, symbols, imports
// (PE / Mach-O fall back to a string-table scan). Call edges are inferred, not disassembled.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const T = (SMS.topology = SMS.topology || {});
  const { builder, addSandbox, slug, hex } = T;

  const DANGEROUS = new Set(['gets', 'strcpy', 'strcat', 'sprintf', 'vsprintf', 'printf', 'fprintf', 'scanf', 'sscanf', 'system', 'popen', 'execve', 'execl', 'execlp', 'execvp', 'memcpy', 'strncpy', 'realpath', 'getwd', 'alloca', 'dlopen']);
  const MACHINES = { 3: 'x86', 40: 'ARM', 62: 'x86-64', 183: 'AArch64', 243: 'RISC-V', 8: 'MIPS', 20: 'PowerPC', 21: 'PPC64' };

  function parseElf(buf) {
    const dv = new DataView(buf);
    const u8 = new Uint8Array(buf);
    if (u8.length < 52 || u8[0] !== 0x7f || u8[1] !== 0x45 || u8[2] !== 0x4c || u8[3] !== 0x46) return null;
    const is64 = u8[4] === 2;
    const le = u8[5] === 1;
    const u16 = (o) => dv.getUint16(o, le);
    const u32 = (o) => dv.getUint32(o, le);
    const uN = (o) => (is64 ? Number(dv.getBigUint64(o, le)) : u32(o));
    const type = u16(16);
    const machine = u16(18);
    const entry = uN(24);
    const shoff = is64 ? uN(40) : u32(32);
    const shentsize = u16(is64 ? 58 : 46);
    const shnum = u16(is64 ? 60 : 48);
    const shstrndx = u16(is64 ? 62 : 50);
    const sections = [];
    for (let i = 0; i < shnum && shoff + (i + 1) * shentsize <= u8.length; i += 1) {
      const o = shoff + i * shentsize;
      sections.push({
        nameOff: u32(o), type: u32(o + 4),
        addr: is64 ? uN(o + 16) : u32(o + 12),
        offset: is64 ? uN(o + 24) : u32(o + 16),
        size: is64 ? uN(o + 32) : u32(o + 20),
        link: is64 ? u32(o + 40) : u32(o + 24),
        entsize: is64 ? uN(o + 56) : u32(o + 36)
      });
    }
    const cstr = (off) => { let s = ''; for (let i = off; i < u8.length && u8[i] && s.length < 120; i += 1) s += String.fromCharCode(u8[i]); return s; };
    const shstr = sections[shstrndx];
    sections.forEach((s) => { s.name = shstr ? cstr(shstr.offset + s.nameOff) : ''; });
    const symbols = [];
    sections.filter((s) => s.type === 2 || s.type === 11).forEach((symtab) => {
      const strtab = sections[symtab.link];
      if (!strtab) return;
      const ent = symtab.entsize || (is64 ? 24 : 16);
      for (let off = symtab.offset; off + ent <= symtab.offset + symtab.size && off + ent <= u8.length; off += ent) {
        const nameOff = u32(off);
        const info = is64 ? u8[off + 4] : u8[off + 12];
        const shndx = is64 ? u16(off + 6) : u16(off + 14);
        const value = is64 ? uN(off + 8) : u32(off + 4);
        const size = is64 ? uN(off + 16) : u32(off + 8);
        const stype = info & 0xf;
        if (stype !== 2 && !(stype === 0 && shndx === 0 && nameOff)) continue;
        const name = cstr(strtab.offset + nameOff).split('@')[0];
        if (!name) continue;
        symbols.push({ name, value, size, defined: shndx !== 0, dyn: symtab.type === 11 });
      }
    });
    return { format: `ELF${is64 ? '64' : '32'}`, arch: MACHINES[machine] || `machine ${machine}`, entry, type: { 1: 'REL', 2: 'EXEC', 3: 'DYN', 4: 'CORE' }[type] || type, sections, symbols };
  }

  function strings(u8, min = 5, cap = 4000) {
    const out = [];
    let cur = '';
    for (let i = 0; i < u8.length && out.length < cap; i += 1) {
      const c = u8[i];
      if (c >= 32 && c < 127) cur += String.fromCharCode(c);
      else { if (cur.length >= min) out.push(cur); cur = ''; }
    }
    return out;
  }

  function fromBinary(buf, filename = 'binary') {
    const u8 = new Uint8Array(buf);
    const elf = parseElf(buf);
    const strs = strings(u8);
    const fmtStrings = strs.filter((s) => /%[-0-9.]*[sdxnpu]|\/bin\/sh|password|secret|token|admin/i.test(s)).slice(0, 5);
    let format = 'unknown';
    if (u8[0] === 0x4d && u8[1] === 0x5a) format = 'PE';
    else if ([0xfeedface, 0xfeedfacf, 0xcefaedfe, 0xcffaedfe].includes(new DataView(buf).getUint32(0))) format = 'Mach-O';
    const b = builder({ label: filename, sub: elf ? `${elf.format} ${elf.arch} · ${elf.type} · entry ${hex(elf.entry)}` : `${format} · ${u8.length.toLocaleString()} bytes · strings only` }, 'parsed');
    const input = b.add('input', 'Process input', 'subsystem', 'core', { sub: 'argv · stdin · env' });
    const argv = b.add('argv', 'argv[1]', 'endpoint', input, { sub: 'attacker controlled' });
    b.add('stdin', 'stdin', 'endpoint', input);

    let imports = [];
    let funcs = [];
    if (elf) {
      const keep = elf.sections.filter((s) => s.name && /^\.(text|data|rodata|bss|plt|got|init|fini|dynamic)/.test(s.name)).slice(0, 7);
      const secIds = {};
      keep.forEach((s) => { secIds[s.name] = b.add(`sec-${slug(s.name)}`, s.name, 'section', 'core', { sub: `${hex(s.addr)} · ${s.size}B` }); });
      const seen = new Set();
      elf.symbols.forEach((sym) => {
        if (seen.has(sym.name)) return;
        seen.add(sym.name);
        if (sym.defined && sym.value) funcs.push(sym);
        else if (!sym.defined) imports.push(sym);
      });
      funcs = funcs.filter((f) => !/^(_|frame_dummy|register_tm|deregister_tm|__do_global)/.test(f.name) || f.name === '_start').sort((a, c) => (a.name === 'main' ? -1 : c.name === 'main' ? 1 : a.value - c.value)).slice(0, 14);
      const textId = secIds['.text'] || b.add('sec-text', '.text', 'section', 'core');
      funcs.forEach((f) => b.add(`fn-${slug(f.name)}`, f.name, 'function', textId, { sub: `${hex(f.value)}${f.size ? ` · ${f.size}B` : ''}` }));
      const pltId = secIds['.plt'] || secIds['.got'] || b.add('sec-imp', 'imports', 'section', 'core');
      imports = imports.filter((i) => DANGEROUS.has(i.name) || !/^_/.test(i.name)).sort((a, c) => (DANGEROUS.has(c.name) ? 1 : 0) - (DANGEROUS.has(a.name) ? 1 : 0)).slice(0, 16);
      imports.forEach((imp) => b.add(`imp-${slug(imp.name)}`, imp.name, DANGEROUS.has(imp.name) ? 'sink' : 'import', pltId, { sub: DANGEROUS.has(imp.name) ? 'dangerous import' : 'libc' }));
      const roId = secIds['.rodata'];
      if (roId) fmtStrings.forEach((s, i) => b.add(`str-${i}`, JSON.stringify(s.slice(0, 20)), 'string', roId));
    } else {
      const known = strs.filter((s) => DANGEROUS.has(s) || /^(printf|puts|malloc|free|strlen|read|write|open|socket|recv|send)$/.test(s));
      const impId = b.add('sec-imp', 'imports', 'section', 'core', { sub: 'from string table' });
      [...new Set(known)].slice(0, 14).forEach((n) => { imports.push({ name: n }); b.add(`imp-${slug(n)}`, n, DANGEROUS.has(n) ? 'sink' : 'import', impId); });
      const strId = b.add('sec-str', 'strings', 'section', 'core', { sub: `${strs.length} printable` });
      fmtStrings.forEach((s, i) => b.add(`str-${i}`, JSON.stringify(s.slice(0, 20)), 'string', strId));
    }
    addSandbox(b);
    const main = funcs.find((f) => f.name === 'main');
    const sink = imports.find((i) => DANGEROUS.has(i.name));
    const path = [argv, main ? `fn-${slug(main.name)}` : null, sink ? `imp-${slug(sink.name)}` : null].filter(Boolean);
    if (path.length >= 2) b.chain(path);
    if (main) funcs.filter((f) => f !== main).slice(0, 4).forEach((f) => b.call(`fn-${slug(main.name)}`, `fn-${slug(f.name)}`));
    return b.done({
      lens: 'binary',
      attackPath: path, entryId: argv, sinkId: path[path.length - 1], guardLink: path.length >= 2 ? path.slice(-2) : null,
      findings: { format: elf ? elf.format : format, arch: elf ? elf.arch : '', functions: funcs.length, imports: imports.length, dangerous: imports.filter((i) => DANGEROUS.has(i.name)).map((i) => i.name), strings: strs.length }
    });
  }

  Object.assign(T, { DANGEROUS, parseElf, strings, fromBinary });
})();
