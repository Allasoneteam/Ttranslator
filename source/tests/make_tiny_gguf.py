# Builds a tiny random-weight llama-architecture GGUF with a byte-level tokenizer and a chat template.
# Only for testing the launcher/UI plumbing: its output is gibberish.
# Usage: make_tiny_gguf.py <out.gguf> <seed> <padding_MB>
# Needs numpy and the gguf package (pip install numpy gguf), or LLAMA_CPP_DIR pointing to a llama.cpp checkout.
import os, sys
if os.environ.get('LLAMA_CPP_DIR'):
    sys.path.insert(0, os.path.join(os.environ['LLAMA_CPP_DIR'], 'gguf-py'))
import numpy as np
import gguf

def bytes_to_unicode():
    bs = list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
    cs = bs[:]
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b); cs.append(256 + n); n += 1
    return dict(zip(bs, [chr(c) for c in cs]))

def main(path, seed, pad_mb):
    rng = np.random.default_rng(seed)
    b2u = bytes_to_unicode()
    tokens = [b2u[b] for b in range(256)]
    merged = b2u[ord('e')] + b2u[ord(' ')]
    tokens.append(merged)                       # one merge so the merges array is not empty
    specials = ['<s>', '</s>', '<|user|>', '<|assistant|>']
    tokens += specials
    types = [1] * 257 + [3] * len(specials)
    n_vocab = len(tokens)
    n_embd, n_ff, n_layer, n_head = 64, 128, 2, 4

    w = gguf.GGUFWriter(path, 'llama')
    w.add_name('tiny-test-model')
    w.add_context_length(4096)
    w.add_embedding_length(n_embd)
    w.add_block_count(n_layer)
    w.add_feed_forward_length(n_ff)
    w.add_head_count(n_head)
    w.add_head_count_kv(n_head)
    w.add_layer_norm_rms_eps(1e-5)
    w.add_rope_dimension_count(n_embd // n_head)
    w.add_vocab_size(n_vocab)
    w.add_file_type(gguf.LlamaFileType.ALL_F32)
    w.add_tokenizer_model('gpt2')
    w.add_tokenizer_pre('default')
    w.add_token_list(tokens)
    w.add_token_types(types)
    w.add_token_merges([b2u[ord('e')] + ' ' + b2u[ord(' ')]])
    w.add_bos_token_id(257)
    w.add_eos_token_id(258)
    w.add_add_bos_token(False)
    w.add_chat_template("{% for m in messages %}<|{{ m['role'] }}|>{{ m['content'] }}{% endfor %}{% if add_generation_prompt %}<|assistant|>{% endif %}")
    if pad_mb:
        # dummy metadata blob so that the file is large enough to watch a download progress
        w.add_string('test.padding', 'x' * (pad_mb * 1024 * 1024))

    f32 = lambda *shape: (rng.standard_normal(shape) * 0.08).astype(np.float32)
    ones = lambda n: np.ones(n, dtype=np.float32)
    w.add_tensor('token_embd.weight', f32(n_vocab, n_embd))
    w.add_tensor('output_norm.weight', ones(n_embd))
    out = f32(n_vocab, n_embd)
    out[258] -= 0.5          # EOS a bit less likely, so answers are not empty
    w.add_tensor('output.weight', out)
    for i in range(n_layer):
        p = f'blk.{i}.'
        w.add_tensor(p + 'attn_norm.weight', ones(n_embd))
        for t in ('attn_q', 'attn_k', 'attn_v', 'attn_output'):
            w.add_tensor(p + t + '.weight', f32(n_embd, n_embd))
        w.add_tensor(p + 'ffn_norm.weight', ones(n_embd))
        w.add_tensor(p + 'ffn_gate.weight', f32(n_ff, n_embd))
        w.add_tensor(p + 'ffn_up.weight', f32(n_ff, n_embd))
        w.add_tensor(p + 'ffn_down.weight', f32(n_embd, n_ff))
    w.write_header_to_file()
    w.write_kv_data_to_file()
    w.write_tensors_to_file()
    w.close()

if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
