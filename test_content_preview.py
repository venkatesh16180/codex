# test_content_preview.py -- Phase 15
#
# Locks in the fix for both real front-matter bugs found and fixed by hand in
# Phase 13, using fixture text verified against the real find_real_content_start
# (not reconstructed from memory -- checked interactively against the real
# function before being written here).
from content_preview import find_real_content_start, looks_like_front_matter


def test_numeric_toc_dump_skipped():
    """Rich Dad Poor Dad shape: copyright/legal boilerplate, then a raw
    page-number TOC dump, then real content. Verified: both the copyright
    chunk (keyword match) and the numeric dump (alpha-ratio < 0.5) are each
    independently flagged as front matter by looks_like_front_matter."""
    copyright_chunk = 'Copyright (c) 1997. All rights reserved. No part of this publication may be reproduced.'
    toc_chunk = '12\n13\n14\n15\n16\n17\n18\n19\n20'
    real_chunk = 'Rich dads acquire assets. Poor dads acquire liabilities that they think are assets.'

    assert looks_like_front_matter(copyright_chunk)
    assert looks_like_front_matter(toc_chunk)
    assert not looks_like_front_matter(real_chunk)

    chunks = [{'chunk_text': copyright_chunk}] * 3 + [{'chunk_text': toc_chunk}] * 4 + [{'chunk_text': real_chunk}] * 3
    assert find_real_content_start(chunks) == 7


def test_editorial_foreword_not_mistaken_for_real_content():
    """How to Win Friends shape: a legitimate, alpha-heavy editorial foreword
    -- normal prose, no keyword match, high alpha ratio. Verified against the
    real function: it is NOT flagged as front matter at all, so the 3-clean-
    chunk run starts immediately at index 0. This is the documented, known
    limitation (agent.py's PREVIEW_CHUNK_COUNT widening is the actual fix for
    this case, not this function) -- this test asserts the current, confirmed
    behavior, not the ideal one."""
    foreword_chunk = 'In revising this edition, we have sought to preserve the original spirit of the author while updating certain examples for a modern reader.'
    real_chunk = 'You can make someone want to do what you want them to do by seeing the situation from the other person'

    assert not looks_like_front_matter(foreword_chunk)

    chunks = [{'chunk_text': foreword_chunk}] * 5 + [{'chunk_text': real_chunk}] * 3
    assert find_real_content_start(chunks) == 0