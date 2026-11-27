.text
.align 2
.global asm_integer_bench
.type asm_integer_bench, %function
asm_integer_bench:
    mov x1, x0
    mov x2, #0x1234
    mov x3, #0x5678
    mov x4, #0x9abc
1:
    madd x2, x2, x3, x4
    eor x4, x2, x3
    add x3, x3, #17
    ror x2, x2, #7
    subs x1, x1, #1
    b.ne 1b
    eor x0, x2, x3
    ret
.size asm_integer_bench, .-asm_integer_bench

.align 2
.global asm_neon_bench
.type asm_neon_bench, %function
asm_neon_bench:
    mov x1, x0
    movi v0.4s, #1
    movi v1.4s, #3
    movi v2.4s, #7
2:
    mla v0.4s, v1.4s, v2.4s
    add v1.4s, v1.4s, v2.4s
    subs x1, x1, #1
    b.ne 2b
    addv s0, v0.4s
    fmov s0, s0
    ret
.size asm_neon_bench, .-asm_neon_bench
