# DRISHTI Project -- Handover

**Prepared:** September 24, 2026  
**Updated:** September 30, 2026 (task 4.6)  
**Workspace:** `D:\sih\main_project`  
**Frontend:** `D:\sih\main_project\frontend`

## Resume from here

### Last Completed Task

**Task 4.6 -- each line group is scored on its own glyph heights and on the
leading its neighbours show, and both scores are ratios rather than
constants, so nothing new was decided about what a glyph is.**
`filter_lines(lines)` and the two module constants `LINE_MAX_HEIGHT_SPREAD`
(1/3) and `LINE_MAX_SPACING_SPREAD` (0.25) in
`backend/app/pipeline/tier0/mrz_region.py`, with 20 new tests in
`backend/tests/unit/test_mrz_region.py`. **The verified result is `1711`
backend (`20` of them new) and `scripts/check-all.ps1` exits 0.** `__all__`
is ten names; the source-side rule test was updated to match and still holds
(no `raise`, no second error type, and `MrzComponent` is still data and
nothing else).

**The two scores are measured against the group, because a constant would be
a fifth glyph-size threshold in a module that already holds four.** A line's
own glyph heights spread about its own **median**, and its spacing to its
nearest neighbour departs from the **tightest spacing the set shows** -- the
leading. Both are dimensionless, so a page photographed at another scale
answers the same, which is the whole reason 4.3's record is in pixel counts
and 4.6's bands are not. Nothing else is filtered and no record is rebuilt:
the groups that come back are the groups that went in, in the order they were
handed over.

**The stray line is the test the task asks for, and it is drawn so that only
one of the two scores can refuse it.** `ERIKSSON<<ANNA<MARIA` goes at the top
of the fixture page at `(40, 20)`, in `upright_mrz`'s own font, scale and
thickness: measured, its glyphs are **13 to 15 rows** tall -- exactly the
MRZ's own -- so the height score passes it at a spread of **0.14**, and the
only thing wrong with it is where it sits. It arrives as a **third group** at
rows 5-20, 4.5 groups it without pre-judging it, and `filter_lines` discards
it while the two printed lines come back as *the very groups the page without
the stray produced* (by identity, not by value). A stray drawn smaller or in
another face would have been discardable on height as well, and the test would
then have shown that *either* score refuses it rather than that the spacing
one does.

**The leading is the tightest spacing and a line is judged on the nearest of
its two, and each half has a wrong answer it was chosen against.** The
*loosest* spacing as the reference discards both MRZ lines on the stray page
and keeps the stray. Scoring the *pair* rather than the line would have to
discard both members of a mismatched pair, and one of them is a real MRZ line
-- which is why the score asks for each line's *nearest* spacing. Both
mutants are caught.

**Two lines cannot be told apart by this step, and that is arithmetic rather
than a threshold.** Two groups have one spacing between them, so the spacing
axis rejects nothing until a third group exists -- which is why the task's
test needs a third line, and why the limit is written down: a stray printed
*within* a quarter of the leading survives (measured **0.14**, on a page
carrying the same name line 25 rows above the MRZ) and so does one printed
*tighter* than the leading, which is what a line caught between two MRZ lines
looks like. What catches a page with three lines on it is 4.7's line count
and 4.10's cell count.

**A line is all-or-nothing here, and the task's own wording decided it.** One
mark a third off the line's median discards the line with it: 4.10 would
otherwise be handed a cell for a character the cut invented, which is a worse
failure than losing a line a re-scan finds again.

**The numbers both bands are sized from are measured, and one of them is a
single reading.** On all four captures 4.2 builds the leading is exactly
**70** and the worst line spreads **2 rows on a median of 14** (0.14), so the
height band at a third is more than twice the worst thing the fixture does,
and the spacing band at a quarter is **17.5 rows**, more than the tallest
glyph on the page (15). The height band is also held *below* the spread 4.4's
own band admits for a line of these glyphs -- (24 - 8) / 15 = 1.07 -- which is
the whole reason the score exists: 4.4 judges each blob on its own and this
judges the line they share a baseline with, so a 10-by-10 speck beside a
15-row glyph is a line 4.4 could not refuse. **The spacing band has one
measurement behind it and is held to its rule until 4.14's generator prints
three lines: re-derive both bands from that page, not from these numbers.**

**Which statistic the reference is, is pinned, and the median needed the band
edge to be visible to be told from the mean.** Four marks of 8, 12, 12 and 12
rows give a median of 12 -- a spread of exactly a third, kept because the edge
is inside the band -- and a mean of 11, which is 0.36 and discarded; a rule
with either number in it is a different rule, and that is the only case that
sees which one is in force. The same is true of the boundaries: rows are whole
numbers, so the spacing edge is probed on a leading of **72** (a quarter of 72
is exactly 18) rather than the fixture's 70, where a quarter is 17.5 and no
row can land on it.

**4.5's note that 4.6 is what throws the greyscale specks away was measured
to be false, and that sentence has been corrected in `group_lines`'s own
docstring and in the Known Issues list below.** The two groups of 2 and 4
blobs are all ten rows tall like each other and a leading apart like each
other, so both scores pass them: a consistency score cannot tell a line of two
blobs from a line of forty. **What a two-blob line is caught by is 4.7's cell
count**, and what a caller that produced it has to fix is 4.2's cut.

**Eighteen mutants were run and all eighteen are caught**: the height score
removed; the spacing score removed; the leading taken as the loosest spacing;
a line judged on its furthest neighbour instead of its nearest; each band
opened to 1.0; the height band closed to 0.1; the reference taken as the mean;
the reference taken as the tallest mark; the zero-height guard removed; the
spacing read in arrival order rather than sorted; the heights spread against
themselves; both boundaries made exclusive; the groups rebuilt as copies; the
lines returned bottom-up; only the first line kept; and nothing discarded at
all. **Three of the eighteen survived the first run and all three were gaps
rather than bad mutants** -- nothing sat exactly on either band edge, so both
boundary mutants passed, and no case separated the median from the mean; hence
the two edge tests and the four-mark case above. The harness was a throwaway
file under `%TEMP%` and was deleted.

Verified: `python -m pytest backend/tests/unit/test_mrz_region.py -q -p
no:faulthandler` reports `131 passed`; `python -m pytest backend/tests -q -p
no:faulthandler` reports `1711 passed` (was 1691) and exits 0; **`scripts/
check-all.ps1` exits 0** (1711 backend, 45 frontend, build); `python -m
compileall -q backend` exits 0. Scope was `mrz_region.py`,
`test_mrz_region.py`, the `tasks.md` marker and note, and this handover; no
other source file and no `lorebook/` file was written, and no writing git
command was run.

**Task 4.5 -- the survivors are put back into the lines they were printed
on, and the edge that decides it is the half-open one every box in this module
already used.** `group_lines(components)` in
`backend/app/pipeline/tier0/mrz_region.py`, with 14 new tests in
`backend/tests/unit/test_mrz_region.py`. **The verified result is `1691`
backend (`14` of them new) and `scripts/check-all.ps1` exits 0.** `__all__`
is nine names; the source-side rule test was updated to match and still holds
(no `raise`, no second error type, and `MrzComponent` is still data and
nothing else).

**The test the task asks for is measured against what the fixture drew rather
than against a bare count, because one group holding both lines answers "2"
as comfortably as two groups holding one line each.** All four captures --
flat, one-sided shadow, low light and sigma-6 grain -- come back as
**exactly 2** lines, each one inside one of the fixture's own two drawn row
bands, and the grouping is a **partition** of the 51 survivors: every record
arrives exactly once, as the record 4.3 measured rather than as a copy. The
lines are rows **105 to 120** and **175 to 190**, and the **55 rows** between
them are larger than the tallest glyph on the page (15) -- which is 4.4's own
stated reason for putting its height ceiling under half the line pitch, so the
gap is now a measurement rather than an argument.

**A line is closed by the running maximum of its members' lower edges, not by
the last one, and that is the decision the first version of this task's test
got wrong.** A blob joins the line above it while its top is *strictly* above
that line's deepest member, so a blob whose top sits exactly on the edge shares
no row with it and opens a new line -- the same half-open edge
`MrzComponent.bbox` already is, and making the comparison inclusive would
merge two lines that merely touch. Comparing against the *previous* blob
rather than the deepest one reads the same on a tidy page and cuts a real
line in half the moment one glyph hangs below its neighbours. **The first
hand-made case had every blob reaching lower than the one before it, which is
exactly the shape where the wrong rule gives the right answer**, so two
mutants survived it: the transitivity is now pinned from both directions
with rows 10-31, 15-17 and 30-32, where the middle blob stops 14 rows short
of where it started and a rule that lost a single row off the edge loses the
line too.

**A blob holding two characters is still one line, and the per-line counts
say so.** Two pairs of neighbours touch at this cut, so line 0 comes back
with 24 blobs for 25 printed characters and line 1 with 27 for 28 (25 and 27
in low light, where a different pair merges). On line 1 the merged blob is
the single 22-wide one among 20 that are 11 wide and none that is wider than
13. 4.10 segments those whether or not they were ever separate glyphs, and
4.7's line count is unaffected either way. The case is also written longhand
-- a 22-wide blob beside an 11-wide one is **one line of two**, not two lines
-- because which pairs merge is a property of the cut and 4.14 replaces it.

**The order is re-sorted rather than inherited, and neither half is 4.3's.**
Lines come back top to bottom, because 4.7 counts them and 4.11 maps a cell
index to a field offset, so which group is line 1 is a question with a wrong
answer; the glyphs inside a line come back left to right, because 4.10
segments along x and its cell 0 has to be the leftmost character. 4.3's
order is down the page and then across it, which is the raster-scan order of
OpenCV's *labelling* rather than the reading order of the document: measured,
the lefts of the 24 glyphs on this fixture's first line are not monotonic in
it, and the test asserts that they are not, so the re-sort cannot quietly be
dropped. Two other arrivals of the same 51 records -- reversed, and rotated
by 27 -- come back as the same two lines.

**The height band is not applied a second time, and that is checkable rather
than promised.** 4.4 wrote the band, and re-applying it here would be one
rule in two places to keep in step. The record that shows it is the signature
4.4 refuses -- 150 by 20, an aspect ratio of 7.5 -- handed straight over
instead of through the filter, which comes back as a line of one. Grouping it
*is* 4.5's whole remit: which blobs share rows.

**Nothing is discarded here, so the handover's standing exposure is now a
measured number rather than a caveat.** A group of one comes back as a group
of one, because "is this line plausible" is 4.6's question -- height
consistency and inter-line spacing -- and answering it here would be a
threshold 4.4 did not write down, which is the same argument 4.4's own band
makes. The six specks of *paper* a greyscale frame leaves behind survive 4.4
for exactly that reason and come back here as **two lines of 2 and 4**,
sitting on the same two baselines the print uses (measured, rows 108-118 and
178-188): 4.6 is what throws them away, and this step reports the grouping it
was handed rather than pre-judging it. The page whose cut went white is
refused by 4.4's height ceiling and arrives here as no lines at all, and a
frame with no ink never had a component -- neither raises, because the package
has exactly one error type and "there is no MRZ here" is not one of them. **A
record of zero height, which `extract_components` cannot produce but a caller
can, has an empty vertical extent and is a line of one** rather than an error.

**Fifteen mutants were run and all fifteen are caught**: the edge made
inclusive; the previous blob taken as the edge rather than the running
maximum; the running maximum off by one; sorted across the page before down;
the inner sort reversed; the inner sort dropped; grouped along x instead of
y; the lower edge read from the right instead of the bottom; everything merged
into a single line; the height band applied again; records rebuilt on both
paths; lists returned instead of tuples; lines of one dropped; and the lines
in reverse order. The harness was a throwaway file at the repo root and was
deleted.

Verified: `python -m pytest backend/tests/unit/test_mrz_region.py -q` reports
`111 passed`; `python -m pytest backend/tests -q -p no:faulthandler` reports
`1691 passed` (was 1677) and exits 0; **`scripts/check-all.ps1` exits 0**
(1691 backend, 45 frontend, build); `python -m compileall -q backend` exits 0.
Scope was `mrz_region.py`, `test_mrz_region.py`, the `tasks.md` marker and
note, and this handover; no other source file and no `lorebook/` file was
written, and no writing git command was run.

**Task 4.4 -- the blobs are sorted into what a character could be and what
could not, and each half of the rule refuses one of the two things a document
frame actually carries.** `filter_glyphs(components)` and the four module
constants `GLYPH_MIN_HEIGHT_PX` (8), `GLYPH_MAX_HEIGHT_PX` (24),
`GLYPH_MIN_ASPECT` (0.2) and `GLYPH_MAX_ASPECT` (2.5) in
`backend/app/pipeline/tier0/mrz_region.py`, with 20 new tests in
`backend/tests/unit/test_mrz_region.py`. **The verified result is `1677`
backend (`20` of them new) and `scripts/check-all.ps1` exits 0.** `__all__` is
eight names; the source-side rule test was updated to match and still holds (no
`raise`, no second error type, and `MrzComponent` is still data and nothing
else).

**The two cases the task names are rejected by different halves, and each test
asserts the other half would have kept the blob.** A printed photo box on the
fixture comes through the real cut as **one component 180 by 120**, whose aspect
ratio is **1.5** - comfortably inside the aspect band - so nothing but the height
ceiling can refuse it. A signature stroke comes through as **one component 150
by 20**, whose height sits *inside* the height band, so nothing but the aspect
ceiling can refuse it. Had either fixture come out the other way round, one half
of the rule would have had no test at all, so both numbers are measured off the
frame in the test before anything is claimed about the blob. **A flat-toned
photo box is the honest version of the first fixture, and the reason is worth
keeping**: a *uniform* patch is not ink to a local cut at all, so what comes
through is the box's outline - measured at 6,148 pixels of the 21,600 the box
spans - and it is still one blob of the box's own size, which is the thing the
band has to refuse.

**The band is in the pixel counts 4.3 reported, and the constants are held to
four rules rather than to this fixture's readings.** Measured across the three
clean captures, a glyph is **13 to 15 pixels** tall with a width-to-height ratio
of **0.29 to 1.47**. The floor is at least half the tallest glyph (8 >= 15/2),
because half is where a mark left by the cut stops being one; the ceiling is
under **half the line pitch** (24 <= 70/2), because a glyph taller than the gap
between two baselines would collide with the line above it and 4.5 groups by
vertical overlap, so a blob spanning both lines would be a group of one; the
aspect floor is a fifth, because the narrowest thing an MRZ prints is a `1` and a
mark five times taller than it is wide is a printed rule, a scratch or a fold;
the aspect ceiling is under three, because a Doc 9303 cell is about square so
even a merged pair is nearer 2:1 - while the signature measures **7.5**.
**4.14 replaces the fixture, so re-run the rules test against the real generator
and re-derive these four numbers from the rules, not from what worked here.**

**The claim 4.3 left for this task held exactly: the grain falls away and the
print does not.** A sigma-6 capture gives **313** components from 4.3 and **51**
after the band - exactly the clean page's glyph count, every survivor inside the
ink the fixture drew - so the floor does the work 4.3 predicted it would, with
no threshold invented after the fact. All three clean captures (51, 51, 52)
come through **unchanged**, which is the other half of the claim: the band is a
filter and not a sieve.

**The blank page is refused here rather than upstream, which is what 4.3's list
was for.** A frame whose cut went white gives 4.3 exactly one component, **600
by 300**, and `filter_glyphs` returns `()` - so the one frame where nothing was
detected cannot reach 4.5 as a line of one enormous glyph and 4.7 as a document
type.

**`area` is on the record and nothing here reads it, pinned non-vacuously.**
Two blobs of the **same 39 pixels** - a 3-by-13 hairline and a 1-by-39 rule -
are given opposite verdicts, so no filter on area alone could produce both
answers whichever direction it were written. The case for needing a third
threshold would be a *photograph whose texture survives the cut as glyph-sized
fragments*, and the answer to that is `ADAPTIVE_C` and `ADAPTIVE_BLOCK_SIZE`
doing their job, not a new number here.

**The survivors are the same records rather than copies, in 4.3's order, and
the height bound is tested before the aspect ratio.** 4.5 groups them and 4.9
fits a line through their centroids, so a rebuilt record would be a second
measurement of the same blob. The ordering is also why a record of zero height -
one OpenCV cannot produce, but a caller can hand over - is refused rather than
dividing by zero.

**Seventeen mutants were run and all seventeen are caught**: either band
dropped; each of the four constants moved (floor down to 1, up to 12; ceiling up
to 40, down to 16; aspect floor to 0.01; aspect ceiling to 10 and to 1.2); the
bounds made exclusive; the aspect ratio computed before the height; the records
rebuilt; the order reversed; a list returned instead of a tuple; an area filter
added; and everything kept. The first run's "list returned" mutant was badly
built - it left a stray bracket and failed at collection rather than on an
assertion - so it was rebuilt properly and fails **11** tests. The harness was a
throwaway directory at the repo root and was deleted.

Verified: `python -m pytest backend/tests/unit/test_mrz_region.py -q` reports
`97 passed`; `python -m pytest backend/tests -q -p no:faulthandler` reports
`1677 passed` (was 1657) and exits 0; **`scripts/check-all.ps1` exits 0**
(1677 backend, 45 frontend, build); `python -m compileall -q backend` exits 0.
Scope was `mrz_region.py`, `test_mrz_region.py`, the `tasks.md` marker and
note, and this handover; no other source file and no `lorebook/` file was
written, and no writing git command was run.

**Task 4.3 -- the ink is numbered and measured, and every number it reports
is a measured pixel count rather than a normalised one.**
`extract_components(binary)` and the frozen record `MrzComponent` in
`backend/app/pipeline/tier0/mrz_region.py`, with 20 new tests in
`backend/tests/unit/test_mrz_region.py`. **The verified result is `1657`
backend (`20` of them new) and `scripts/check-all.ps1` exits 0.** `__all__` is
seven names; the source-side rule test walked the AST instead of grepping and
the claim did not change.

**The plausible count is 51 from 53 printed characters, and the shortfall is
two merged neighbours rather than a loose band.** The ceiling is not a
tolerance -- a blob holds at least one character's ink, so no component can
exist without something behind it -- and that still holds on the frame that
went white. The floor is three quarters of the characters. Three more claims
sit beside the count, because a bare count is satisfied by a single full-page
blob just as comfortably as by two lines of print: the areas **partition the
ink exactly**, every box lies inside the ink `glyph_mask` drew, and the widest
and tallest are **4.2's own numbers read by 4.2's own helper**. The three
clean captures give 51, 51 and 52, so the band is two wide, not one.

**The page is dropped by label, and the frame 4.2 could not fix is what
decides it.** When the page turns white the frame is entirely ink, and
OpenCV numbers the *empty* background anyway, giving it the sentinel row
`[-1, 2147483647, 0, 0, 0]`. Dropping the widest component, the last one, or
the largest-area one therefore reports a **clean page** on the one frame
where the cut has failed, and 4.4 would have nothing left to reject. Dropping
index 0 leaves the single 600-by-300 blob visible, which is what 4.2's
docstring promised 4.3 would see. A second test holds the same rule where the
background is small rather than absent -- a page that is all ink except a
hole -- so a reading that dropped "the biggest blob" would return the hole.

**`CONNECTIVITY = 8`, chosen on a measurement rather than a preference, and
passed by keyword because OpenCV's signature will not let it be passed
otherwise.** A twelve-pixel diagonal stroke is **twelve** components under
4-connectivity and **one** under 8, and MRZ strokes are diagonal. But
`connectedComponentsWithStats`'s documented signature is
`(image[, labels[, stats[, centroids[, connectivity[, ltype]]]]])` -- the
second *positional* parameter is the `labels` **output**, so a call written
`(binary, 8)` binds the 8 there and silently gets the default. The default is
8, which is exactly why it cannot be noticed by looking at the answers: the
positional form returns **one** component on that stroke for both `4` and
`8`, where `connectivity=` returns twelve and one. **4.2's own test helper
`_widest_and_tallest` passes `8` positionally too; its answers are right,
because 8 is the default, but the argument there does not say what it looks
like it says.** Left alone as out of scope, and worth knowing about.

**The list is ordered down the page and then across it, which is not the order
OpenCV hands back.** Labels are numbered in raster-scan order of each
component's first pixel: measured on this fixture, the fourteenth component's
box starts at row 107 and the fifteenth's at row 106. 4.5 groups by vertical
overlap and 4.10 segments along x, so that is the order those two want, and
the test asserts the fixture *is* a frame where OpenCV's own order is
unsorted so the assertion is not vacuous.

**The centroid is the mean of a component's pixels, the box is half-open, and
both were chosen against a specific wrong answer.** An L-shaped blob has
centroid `(7.333, 4.167)` against box centre `(7.0, 5.0)`, and 4.9 fits a
line through these -- a box centre would tilt that fit towards whichever glyph
shape was in the group. The box is `(left, top, left + width, top + height)`
and not OpenCV's inclusive `cv::Rect`, so
`binary[top:top + height, left:left + width]` is exactly the component; a
one-pixel blob at `(6, 4)` is `(6, 4, 7, 5)`, and a test says so explicitly
because `(6, 4, 6, 4)` is the other answer. Every field is a **measured**
pixel count -- tallest 15, widest 22 -- never a normalised one, which is what
this handover asked for so 4.4's band is written against the same integers.
The numbers are converted to plain `int` and `float` on the way out, because
4.4 compares them against a band, 4.5 sorts them, and a record carrying
`numpy.int32` cannot go in a JSON body when 4.13's empty result becomes a
response.

**Nothing is filtered here, and a test says so before 4.4 finds out.** A
sigma-6 grainy capture gives **313** components against the clean frame's 51,
with areas down to a single pixel, while the widest and the tallest component
are identical on both. That is the claim 4.4's height band rests on, restated
through this task's own output, and it is why a filter here would be applying
a threshold nobody wrote down.

**The source-side rule test walked the AST instead of grepping, and the claim
did not change -- 3.14's move applied one part earlier.** It asserted
`"class " not in source` and `"raise " not in source`. The first is a proxy
for a rule that is about *error types*, and 4.3 introduces this module's first
record, which is not one; the second was already a landmine, because
`"raise "` appears in this module's own docstrings while they explain the
rule. An `ast.Raise` walk and a `ClassDef`-bases walk say what the substrings
meant, and a third assertion pins `MrzComponent` as not a `BaseException`. A
fourth test holds the record to **data and nothing else**: seven fields, and
`bbox` and `centroid` as the only public attributes, because a method on it is
where a second judgement about what a glyph is would grow.

**A greyscale frame is accepted and its answer is the page, and that is
written down rather than refused.** A three-channel frame is `cv2.error`
exactly as 4.2 made it. A *greyscale* frame is the other mistake and OpenCV
does not object: it reads every non-zero pixel as ink, so `to_gray`'s own
output handed straight in gives 24 components on this fixture with one 600
pixels wide. That is the page-turned-white failure by another route, and
catching it would need a `raise` this module may not have. A test measures
the answer so the limitation is a number and not a caveat.

**Seventeen mutants were run and all seventeen are caught**: the background
kept, dropped by the wrong label, dropped by position and dropped by size;
the connectivity set to 4 and passed positionally; the sort removed and
sorted across before down; numpy scalars left in; the centroid taken as the
box centre; the box counting the far edge in; the area read as width times
height; height and width swapped; a speckle filter added early; a list
returned instead of a tuple; the record made mutable; and a colour frame
quietly converted. The first run reported 14 of 15 and the survivor was a
badly built mutant rather than a gap -- `list(enumerate(stats))[1:]` is the
same reading as the original -- so it was replaced with three that differ.
Both harnesses were throwaway files at the repo root and were deleted.

Verified: `python -m pytest backend/tests/unit/test_mrz_region.py -q` reports
`77 passed`; `python -m pytest backend/tests -q -p no:faulthandler` reports
`1657 passed` (was 1638) and exits 0; **`scripts/check-all.ps1` exits 0**
(1657 backend, 45 frontend, build); `python -m compileall -q backend` exits 0.
Scope was `mrz_region.py`, `test_mrz_region.py`, the `tasks.md` marker and
note, and this handover; no other source file and no `lorebook/` file was
written, and no writing git command was run.

**Task 4.2 -- the working image is turned into ink, and the cut is local
because 4.1 refused to assume the paper was white.** `to_gray(image)` and
`binarize_inverted(gray)` join `deskew` in
`backend/app/pipeline/tier0/mrz_region.py`, with 27 new tests in
`backend/tests/unit/test_mrz_region.py`. **The verified result is `1638`
backend (`27` of them new) and `scripts/check-all.ps1` exits 0.** `__all__` is
five names; the source-side rule test was updated to match and still holds (no
class, no `raise`).

**The adaptive threshold is the load-bearing word, and it was measured on a
photograph rather than asserted.** On a page whose right half sits at half
brightness, one global Otsu cut -- the estimator `m7_skew` itself reaches
for, and the right answer for a flat scan -- calls **88%** of that half ink
and hands 4.3 a connected component **264 pixels** wide. The local cut calls
**2.9%** of the page, which is what the same page scanned flat gives (2.9%),
and its widest component is one glyph, 22 pixels. One test asserts **both**
halves of that comparison, because a test that only said what the local cut
does could not tell a deliberate choice from a fixture that happened to be
evenly lit.

**The polarity is measured against the fixture's own drawing rather than a
proxy.** `connectedComponentsWithStats` numbers the zero-valued region as
background, so paper at 0 and glyphs at 255 makes the list 4.3 reads *be* the
glyph list, with the page in the one entry to throw away; the other way round
hands 4.3 a full-page foreground component. The test re-draws the same two
lines with `LINE_8`, dilates by a pixel for the anti-aliased fringe
`upright_mrz` paints, and asserts **zero** white pixels outside the glyphs --
the other way round puts about 174,000 pixels of paper out there.

**`ADAPTIVE_C = 10` is this project's own number, and what it risks is written
down rather than claimed away.** Zero is not the neutral choice it looks like:
`THRESH_BINARY_INV` marks a pixel white when it sits *at or below*
`local mean - C`, so at `C = 0` a **uniform** page compares equal to its own
neighbourhood mean and every pixel becomes ink -- 84% of the flat fixture
against 2.9% here. It is also what stops grain running the page white
(sigma-6 grain: 40% ink at 0, 3.0% at 10). **Nothing in this repository can
say how much darker than the paper a genuine MRZ stroke is**: no copy of
Doc 9303, no printed specimen, and the fixture is *drawn*, so its strokes are
255 levels below the paper by construction. A larger offset buys cleaner paper
at the cost of faint print. The number is sized to stop the page turning
white -- the failure that makes 4.3 see one component -- and not to reach
a clean component list, which is 4.4's height band's job.

**`ADAPTIVE_BLOCK_SIZE = 41` is a rule and not a tuned optimum, and that was
measured before it was chosen.** Every odd block from 11 to 61 gives the same
reading on the fixture (ink 2.6%-3.0%, tallest component 15 pixels at every
one), so a test sweeps all 26 and asserts the reading is the module's. The
constant is then pinned on three checkable rules that 41 satisfies: odd
(OpenCV refuses an even neighbourhood), **at least twice a glyph** (or the
window measures the glyph's own level and stops being a cut relative to the
paper), and **under a line pitch** (or a pixel in the gap between two MRZ
lines takes both lines' ink into its mean). Both sizes are measured from the
fixture rather than restated, so 4.14 replacing the generator cannot quietly
invalidate the rule.

**`to_gray` is idempotent, and that is not what `deskew` does on purpose.**
`deskew` refuses a one-channel frame because it would run `m7_skew`'s
estimator on something its author never saw. Here the conversion *is* the job,
so a converted frame is handed straight back -- the same object, not a copy,
as `deskew` does -- and a caller never has to track how many channels it is
holding. The conversion is **weighted luma, not a channel mean**: red 76,
green 150, blue 29, where a mean says all three are 85, which is how blue ink
or a red security tint ends up sitting exactly where black belongs.

**Neither step moves the frame, and the order is held together end to end for
the first time.** One test runs `deskew` on a page tilted 5 degrees, then
`to_gray`, then `binarize_inverted`, and asserts the frame is the one that
went in, the ink is in two row bands, and the ink fraction matches the flat
page within 10%.

**Ten mutants were run against the suite and all ten are caught**: the
polarity flipped, the Gaussian weighting replaced by a box mean, the local cut
swapped for a global Otsu, the offset zeroed, the offset quadrupled, the block
set below one glyph, the block set above the line pitch, luma replaced by a
channel mean, the already-converted short-circuit deleted, and
`binarize_inverted` short-circuited to return its argument. Both harnesses
were throwaway files at the repo root and were deleted.

Verified: `python -m pytest backend/tests/unit/test_mrz_region.py -q` reports
`58 passed`; `python -m pytest backend/tests -q -p no:faulthandler` reports
`1638 passed` (was 1611) and exits 0; **`scripts/check-all.ps1` exits 0**
(1638 backend, 45 frontend, build); `python -m compileall -q backend` exits 0.
Scope was `mrz_region.py`, `test_mrz_region.py`, the `tasks.md` marker and
note, and this handover; no other source file and no `lorebook/` file was
written, and no writing git command was run.

**Task 4.1 -- the working image is rotated upright by the angle `m7_skew`
already measures, and the frame it comes back in is the frame it went in
on.** New `backend/app/pipeline/tier0/mrz_region.py` -- the file `ROADMAP.md`
B1.10 names -- with `deskew(image)`, `skew_deg(image)` and `MAX_DESKEW_DEG`,
and 31 new tests in `backend/tests/unit/test_mrz_region.py`. **The verified
result is `1611` backend (`31` of them new) and `scripts/check-all.ps1` exits
0.**

**The skew angle is measured once, by code this project already ships, and
this is the only step in Part 4 that reuses anything.** `m7_skew` gains one
public function, `text_skew(img, mode=...)`, which returns the **signed**
reading its private estimators have always produced; `assess` now calls it in
both of its branches, so the quality gate and the new helper cannot drift onto
different estimators. Nothing in `mrz_region.py` computes an angle. The reuse
is pinned two ways rather than by a comment: one test asserts
`mrz_region.skew_deg` equals `m7_skew.text_skew` on a real tilted page, and a
second stands a sentinel angle in `m7_skew`'s place and asserts the output is
rotated by exactly that sentinel -- which a local estimator would ignore,
however the fixture happened to be tilted.

**A positive reading is the correction and not the tilt, which is the one
thing about this task that is easy to get backwards.** A page turned `+5`
degrees reads about `-5`, and the rotation is applied *as the reading comes*:
negating it leaves `-9.8` on a fixture that wanted `-5`. The task's own test
reads the corrected page with `m7_skew`'s **other** estimator -- the photo-mode
`minAreaRect`, which shares no code with the scan-mode projection search --
and requires it within 0.5 of level, while the starting page must read over
4, so neither an identity function nor a sign flip passes it. The parametrised
test pairs every rotation with its mirror for the same reason.

**The frame does not move, and that is a decision rather than a shortcut.**
Rotating into a larger canvas loses nothing but offsets every polygon 4.8
emits and every field box 4.12 returns away from the frame the officer is
looking at, and nothing downstream carries an offset. The four new corners are
filled with the image's own per-channel median. `BORDER_REPLICATE` was
measured and rejected: it smears the border into the ink mask, and with it in
place the independent verifier reads `0.00` for *every* image, corrected or
not -- the test could not have told a correct rotation from a wrong one. The
median is a tuple because OpenCV reads a **scalar** `borderValue` as
`(v, 0, 0)` on a three-channel image, so `borderValue=255` fills a white
page's corners **blue**; a corner that binarises as ink hands 4.3 a
full-width false component, and a test asserts the corner's three channels are
equal.

**`MAX_DESKEW_DEG` is `m7_skew.MAX_SKEW_DEG` bound, not a second number, and
the comparison is `>`.** At or past the gate's own pass threshold `m7_skew`'s
search is at the edge of its range, so the angle is an artefact of the search
rather than a measurement, and rotating by it can leave the image *less*
upright than it was. In that case the argument is returned as it arrived -- the
same object, not a copy -- which is also where a blank page lands, since the
scan estimator answers an empty frame with the end of its own search range.
`skew_deg` returning `None` (no text at all) takes the same branch. Two tests
walk both sides of the bound and both signs, and one asserts the exact
boundary *is* applied, so an off-by-one `>=` fails.

**The input is three-channel BGR because that is what `m7_skew` takes, and a
greyscale test was deleted rather than satisfied.** `_scan_skew`'s `cvtColor`
raises on a one-channel image; the alternative, converting quietly inside
`deskew`, would run the estimator on a frame its author never saw and be the
one step in Part 4 nobody could check against the gate that ran before it.
`app.analysis` decodes uploads with `IMREAD_COLOR` for the same reason.

**Gate 1 stopped being a probe and became a test, because this is the file
that could have broken it.** `mrz_region.py` is the first module in the
package to import `cv2`, so one `from .mrz_region import deskew` inside
`td3.py` would have pulled OpenCV into every MRZ reader with nothing in the
suite noticing.
`test_the_character_readers_still_import_without_opencv` runs a bare
interpreter that imports `document`, `td1`, `td2` and `td3` and reports
whether `cv2` or `numpy` landed in `sys.modules`. A second test holds the new
module to 1.9's rule from the source side -- no class, no `raise`, `__all__`
exactly the three names -- and `test_mrz.py`'s existing package-wide scans
now cover `mrz_region.py` without an edit, because `PACKAGE_FILES` is a glob.

**Eight mutants were run against the suite and all eight are caught**: the
sign flipped, a local estimator replacing the call, a scalar border fill, an
enlarged canvas, the bound made exclusive, the bound restated as `12.0`, the
guard deleted, and `deskew` short-circuited to return its argument. The
harness was a throwaway and was deleted.

Verified: `python -m pytest backend/tests/unit/test_mrz_region.py -q` reports
`31 passed`; `python -m pytest backend/tests -q -p no:faulthandler` reports
`1611 passed` (was 1580) and exits 0; **`scripts/check-all.ps1` exits 0**
(1611 backend, 45 frontend, build); `python -m compileall -q backend` exits 0.
Scope was the new `mrz_region.py`, `m7_skew.py`, the new `test_mrz_region.py`,
the `tasks.md` marker and note, and this handover; no other source file and no
`lorebook/` file was written, and no writing git command was run.

**Task 3.14 -- one record for three documents, told apart by a
discriminator, and one function that works out which of the three shapes it
is looking at before it hands the lines to anyone.** `MrzDocument` -- the
frozen dataclass `td3.py` has declared since 3.1 -- is now the common
currency of all three formats, and the new module
`app/pipeline/tier0/document.py` holds `MRZ_SHAPES`, `MRZ_PARSERS`,
`detect_mrz_format(lines)` and `parse_mrz(lines)`. **The verified result is
`1580` backend (`52` of them new, in a new `test_document.py`) and
`scripts/check-all.ps1` exits 0.**

**`MrzDocument` was not moved, and that is a decision rather than an
omission.** 3.6, 3.7 and 3.9 each wrote "no record type is created here, and
that is 3.14's to decide" above their line assemblers, and the decision was
one type rather than three, so the only question left is where it lives. It
stays in `td3.py`, which is where 3.1 put it and where 500 lines of
`test_td3.py` expect it, and `td1.py`, `td2.py` and `document.py` import it
from there. `td1.py` importing from `td3.py` is acyclic -- `td3.py` imports
only `mrz.py` -- and one declaration beats a second shape every time. A test
asserts the three are the same object.

**The dispatcher had nothing to dispatch to, so this task wrote the two
parsers and the two zone gates that 3.6, 3.7, 3.9 and 3.10 all left
explicitly to it.** `validate_td1_lines` (three lines of 30) and
`validate_td2_lines` (two lines of 36) are the twins of 3.11's
`validate_td3_lines`, and `parse_td1(lines)` and `parse_td2(lines)` are the
whole-zone assemblers 3.14's record needs. A TD2's name is read through
`td3.py`'s five-step pipeline -- imported, not reimplemented -- because a TD2
prints the same MRZ name field the TD3 does; the name *field* itself is read
by `td2.py`'s own reader, because 31 characters at 6-36 is not 39 at 1-39.

**The private `_checked_line` stays in both modules, and the handover's "all
six assemblers lose it at once" was not followed.** Removing a width check
from a published function is a breaking change that 264 and 273 existing
tests pin, and it would *open* the hazard 3.7 recorded rather than close it:
a TD1 or TD2 composite computed over a silently short multi-line span comes
back **failed** rather than as an error, which is the worse of the two
failures. What the new gate buys is the thing no reader inside a format can
see -- **a missing third line**, since a TD1's name line is a whole
document's worth of identity data that simply arrives absent. A new test in
each file runs the gate before the readers and asserts the failure is a
`MrzValueError` and never a bare `IndexError`; that test is the one the
mutant harness found a gap in, and it is written because of that.

**`None` means "this format prints no such field", and it is never an empty
string.** Seven attributes are the three layouts' format-specific fields --
a TD3's personal number and its digit, which keep their printed place, and a
TD1's optional data 1 and its digit, its optional data 2, and a TD2's
optional data and its digit, which go at the end of the declaration after
`sources` because no single printed order contains all five. The empty
string would be a lie twice over: it is a width no field in any layout has,
and it is the answer `mrz.parse_date` already gives for six characters it
could not read, so one value would mean two different things depending on
which field it was read from.

**The record carries no reference date and no inferred year, and that is the
decision this handover asked to be written down.** Two nullable year fields
would put two readings of one field on one record -- `"740812"` and `1974` --
and a year is `int | None` *against a reference the record would not carry*,
so the reading would be frozen without the thing that makes it true. A
`reference` attribute is the one shape that could put `datetime.now()` back
at the edge of the package, which `tasks.md` bans inside check logic and
which 3.12 and 3.13 pinned out of `mrz.py` by AST walk. So a caller holding
the record and a date asks `mrz.infer_birth_year(document.date_of_birth,
reference)` directly; the printed field *is* the argument. Four tests hold
it, one an AST walk over `document.py` asserting it names no `datetime` and
neither inference, and one a positive test reading a parsed TD3's dates
through both.

**3.13's substring assertion over the three format modules became an AST
walk, and the claim did not change.** The old test asserted
`"infer_birth_year" not in source`; 3.14's docstrings name both functions in
order to explain why the record carries no century, so a substring test would
have had to ban the sentences documenting the decision it protects -- the
same reason 3.13 walked `mrz.py` rather than reading it. A call is a `Name`
in the code; a word in a comment is not.

**The three shapes are disjoint, so the dispatch is a lookup and never a
tiebreak, and a zone whose lines differ in width is refused rather than
dispatched on its first line.** Three lines of 30 is a TD1, two of 36 a TD2,
two of 44 a TD3. Eleven unrecognised shapes are tested -- no lines, one
line, a missing name line, a fourth line, three lines of 44, four of 36, a
line one character short on either line, a ragged zone, non-string lines,
and a zone with one good line and one integer -- and each is refused by
`MrzValueError` with a message naming the count, the widths and the three
shapes this package does read, and **never a character**, because widths are
shape and the characters are the identity data the screening is about.

**A TD1's `name`, `surname` and `given_names` are `None`, and that is a gap
rather than a decision.** Line 3 still has no reader; the thirty characters
are in `sources` under the layout's own `name` key, so nothing is lost and a
later task fills the three attributes without changing this type.

**Thirteen mutants were run against the suite and all thirteen are caught**:
the discriminator hard-coded to `"TD3"` in either parser, a per-format field
left `None`, a per-format field made an empty string, **the zone gate deleted
from `parse_td1`**, a TD1's name or surname invented, ragged zones accepted,
an unrecognised shape defaulted to TD3, the zone measured twice, the refusal
message echoing the characters, the zone not materialised, and the one-string
guard removed. The gate mutant is the one worth remembering: it **passed the
suite** until the gate-ordering tests were written, which is why they exist
now.

Verified: `python -m pytest backend/tests/unit/test_document.py -q` reports
`52 passed`; `python -m pytest backend/tests -q -p no:faulthandler` reports
`1580 passed` (was 1503) and exits 0; **`scripts/check-all.ps1` exits 0**
(1580 backend, 45 frontend, build); `python -m compileall -q backend` exits 0;
importing `document`, `td1`, `td2` and `td3` loads neither `cv2` nor
`numpy`, so Gate 1 holds. Scope was `td3.py`, `td1.py`, `td2.py`, the new
`document.py`, the five MRZ test files (new `test_document.py`, plus the
`__all__` and field-list pins in `test_td1.py`/`test_td2.py`/`test_td3.py` and
the AST walk in `test_mrz.py`), the `tasks.md` marker and note, and this
handover; no other source file and no `lorebook/` file was written, and no
writing git command was run. The mutant harness was a throwaway at the repo
root and was deleted.

**Task 3.13 -- an expiry is read forwards and a birth backwards, so the two
rules are two functions, and the expiry rule has no band because it does not
need one.** `mrz.py` carries `infer_expiry_year(text, reference) -> int |
None` beside 3.12's `infer_birth_year`, in `__all__` (fourteen names in all).
**The implementation was already in `mrz.py` from an interrupted attempt and
was not modified by this task** -- what was missing was the entire test
section, plus one 3.12 scope assertion this task retires by design. The
verified result is `428 passed` in `test_mrz.py` (52 new) and `1503` backend.

**The rule is the nearest year carrying the two printed digits that has not
already passed**, and the candidate pair is 3.12's with the sign flipped:
`century + YY` and `century + 100 + YY`, most recent first. A birth walks
backwards and a birth's most recent candidate is at most 100 years old; an
expiry walks forwards and the nearest match ahead is likewise within the
century the two digits already repeat over.

**The comparison admits the day itself, and that is the one place the two
rules are not mirror images.** A document is valid *through* the day it
expires, so an expiry today is this year -- the same answer a birth today
gets, because a birth today has already happened. **The next day the same six
characters mean a century on**, and a test pins all three of those days for
both rules in one place: `"260929"` is a birth of today and an expiry that
lapsed yesterday; `"260930"` is 2026 for both; `"261001"` is a birth a
century back and an expiry still valid this year. A reader comparing the
years alone would get `"260101"` and `"260930"` the same way round, and the
`"260101"` row is the one that pins the comparison being on the whole date.

**There is no `MAX_EXPIRY`, and the absence is a decision with its reasoning
written next to it rather than a gap.** `MAX_BIRTH_AGE` exists because nobody
is 121 -- a fact about a person, which the six printed characters cannot
supply. An expiry has no such fact, and the bound it does have is
arithmetic: two digits repeat every hundred years, so the nearest year that
has not passed is at most a century away, and a third century is further than
the answer can ever be. Three tests make that checkable rather than asserted.
The sweep asserts `0 <= found - reference.year <= 99` on all 700 cases. The
sweep asserts `unplaceable == 0`, which is the count that separates the two
sweeps -- 3.12's leaves `None`s behind when the band runs out and this one
cannot, because there is nothing to run out of. And an AST walk asserts
`MAX_BIRTH_AGE` is not among `infer_expiry_year`'s `ast.Name` nodes while it
**is** among `infer_birth_year`'s, so the comparison is between two real
bodies. The walk is on the code rather than the source text because the
docstring names the constant in order to explain why this rule does not use
it, and a substring test would have to ban the sentence documenting the rule.

**The leap-day question bites differently here, and this is the task's
distinguishable case.** A birth reads backwards and always has a century in
hand, so its `None` needs a century that is both too old *and* not a real
day; an expiry reads forwards and can simply **run out of real days**. The
same field, read against the same reference, gives different *kinds* of
answer: `"000229"` is 2000 for a birth in 2026 and `None` for an expiry --
2000 has passed and 2100 was not a leap year. The run-out is long and is a
real property of the Gregorian calendar rather than a quirk: 2100, 2200 and
2300 are all non-leap centuries, so the same field is unplaceable from 2000
all the way to 2400 and returns 2400 when read against 2400. **The one-day
boundary pair is 2000-02-28 ? 2000 and 2000-03-01 ? `None`**: on the 28th the
nearest century *is* the leap year, and the next day it has passed and the
next century never had a 29th of February. A birth reading that field says
2000 on the second of those two days, which is the sharpest single pair in the
package.

**The two gates and the three `None`s are 3.12's and share one function.**
`_readable_date` (`parse_date`, then `date_fault`) and `_is_a_real_day` are
the only things the two rules have in common, and fifteen unreadable,
impossible and wrong-width fields are asserted to return `None` from **both**,
row for row, rather than the sharing being described in a comment. The third
`None` -- no century makes this a real day that has not passed -- is the
expiry-only one above. A bad `reference` still raises `MrzValueError` before
the field is read, and the two functions now share one message, asserted
equal, because it is the same mistake about the same thing.

**3.12's scope assertion was updated rather than deleted, and the replacement
is stronger.** `test_the_rule_is_a_date_of_birth_rule_and_nothing_is_wired_to_it_yet`
asserted `not hasattr(mrz, "infer_expiry_year")` -- a claim this task makes
false by landing. It is now
`test_the_two_rules_are_separate_functions_and_neither_is_wired_to_a_validator`,
which asserts both functions exist, are not the same object, have different
sources, take the same `(text, reference)` signature, are referenced by none
of `td1`/`td2`/`td3`, and **genuinely disagree** -- `("740930", REFERENCE)` is
1974 for a birth and 2074 for an expiry. **A test that only said "the second
does not exist yet" would have stopped protecting anything the moment the
second arrived**, which is the reason the handover gave for updating rather
than dropping it. A five-row disagreement table measured against one
reference is the direct guard against the `kind=` flag the handover warned
about: a single function with an argument would pass every other test in the
file and fail that one.

**The whole rule is measured rather than remembered.** All one hundred
printed years are read against the same seven reference dates 3.12 used -- 700
cases, the count asserted -- and compared with the rule restated longhand in
the test, the `TEST_MONTH_DAYS` technique again, with the hundred-year walk
written out and **no band in the copy**, so a wrong constant in `mrz` cannot
be laundered through a shared expectation. Every answer is then checked
against the three properties the rule claims: these two digits, not already
passed, and within a century. **Ten mutants were run against the suite and
all ten are caught** -- the direction flipped, the farthest century tried
first, the day itself excluded, the leap-day check deleted, `MAX_BIRTH_AGE`
borrowed as a band, the century hard-coded at 2000, the year compared without
the month and day, the readability gate dropped, the reference type gate
dropped, and the two printed year digits read as the day. (The harness's first
leap-day mutant was a no-op that only stripped a comment, and was corrected
and re-run before the count above was recorded.)

Verified: `python -m pytest backend/tests/unit/test_mrz.py -q` reports `428
passed` (376 before this task's tests); `python -m pytest backend/tests -q -p
no:faulthandler` reports `1503 passed` (was 1451) and exits 0; **`scripts/
check-all.ps1` exits 0** (1503 backend, 45 frontend, build); `python
-m compileall -q backend` exits 0; importing `mrz` loads neither `cv2` nor
`numpy`, so Gate 1 holds. Scope was `test_mrz.py`, the `tasks.md` marker and
note, and this handover; `mrz.py` was already complete and was not touched, no
other source file and no `lorebook/` file was written, and no writing git
command was run. The mutant harness and a Gate 1 probe were throwaways at the
repo root and were deleted.

**Task 3.12 -- two printed digits of year become a four-digit year, against a
reference date the caller injects, and `None` is now a three-way answer.**
`mrz.py` gains `MAX_BIRTH_AGE = 120`,
`infer_birth_year(text, reference) -> int | None` and the private
`_is_a_real_day(year, month, day)`. Two names in `__all__` (thirteen in all).

**The rule is one sentence and it is the task's, completed: the most recent
year carrying the two printed digits that has already happened, was a day that
year had, and is no more than `MAX_BIRTH_AGE` years before the reference.**
Only two centuries are ever candidates -- `century + YY` and
`century - 100 + YY` -- and a third is past the band whatever it holds, so it
is not weighed. The most recent is tried first, so the older century is a
fallback rather than a preference.

**The task's sentence is half a rule, and the half it leaves out is that a
birth has not happened yet.** Read literally, "a `YY` implying a person older
than ~120 years maps to the previous century" makes the *current* century the
default, and on a 2026 document that sends `"74"` to 2074: a birth 48 years in
the future. So the previous century is reached two ways, and both are written
down rather than one being assumed -- a date the reference has not reached, and
a century further back than `MAX_BIRTH_AGE`. **The band is also where the
task's 120 is observable at all**, because the "not yet" test alone can never
need it (the two digits repeat every 100 years, so the most recent past
reading is at most 100 years old): read on 2120-12-31, `"000229"` is 2000 -- a
real day, exactly 120 years back -- and read on 2121-01-01 it is `None`,
because 2100 had no 29th of February and the century before that is 121. That
one-day pair is the boundary test the task asked for, and it is a *date* pair
rather than a year pair because the "not yet" comparison is on the whole date:
`"260930"` read on the 30th is 2026, `"261001"` read on the 30th is 1926.

**The comparison is a full date, and that is not decoration.** A holder born
on the day the document is read is not a century away, and a holder born
yesterday is not in the future; only a *year* comparison gets both wrong, and
it gets them wrong in opposite directions. Two tests pin it -- a `>=` mutant
on the comparison, and `"060101"` read on 2005-12-31 (1906) against 2006-01-01
(2006).

**The leap-year question 3.11 deferred by putting 29 into February's maximum
is answered here, and `"020229"` is the row that had to be written to answer
it.** Read in 2026 its two candidates are 2002 and 1902, **neither of which
had a 29th of February**, so a field `date_fault` calls perfectly good gets no
year at all. `MONTH_DAYS[1]` stays 29: the range check still cannot know the
century, and now it does not have to, because the century arrives separately
and the leap-year question lives with it. `calendar.isleap` is the only
calendar rule in the module, and it is four lines.

**`None` is now three answers the caller cannot tell apart, and all three are
the same sentence: this document does not tell us.** The six characters are not
all digits; `date_fault` names a month or day that cannot be one, so there is
no real date to place in a century at all; or no century in the
`MAX_BIRTH_AGE` window makes those six characters a real past day. **A guess is
worse than a gap**, because an officer reading a year this project invented has
no way to know it was invented. The two gates are asked in 3.11's order --
`parse_date` first, then `date_fault` -- and the first run of the tests caught
the mistake of asking only `date_fault`, which answers `None` both for "I could
not read it" and for "there is no fault here", so a field of six letters would
have been read as a year of zero.

**A bad `reference` raises where a bad date field does not, and the asymmetry
is the point.** A reference date is never a fact about a document, so a caller
who has not injected one is told (`MrzValueError`, added to 1.9's bad-call
matrix) rather than answered `None`: reporting a screening that went wrong as
a document nobody could read is the one confusion this package cannot have.
`datetime.datetime` is *not* refused, since it subclasses `datetime.date`.
`datetime.now()` and `date.today()` are pinned out of the module by an AST
walk rather than a substring, because the docstrings name `datetime.now()` in
order to say it is not used.

**Nothing is wired to it, and that is three tests rather than a promise.** No
format module references `infer_birth_year` (the validators judge range only,
which 3.11's note put 3.12 and 3.13 *after* it on purpose), `MrzDate` still
holds exactly three fields, and `mrz` has no `infer_expiry_year` -- 3.13's, and
a different rule, which is why this one is named for the date it answers for
rather than `infer_century` with a flag.

**The whole rule is measured rather than remembered.** Every printed year
`00`-`99` is read against seven reference dates -- 700 cases, the count
asserted -- and compared with the rule restated longhand in the test, the
`TEST_MONTH_DAYS` technique, so a wrong rule cannot agree with itself. Each
answer is then checked against the three properties the rule claims: these two
digits, in the past, no more than 120 years back. **Fourteen mutants were run
against the suite and all fourteen are caught**: the "not yet" comparison as
`>=`, the band removed, the band closed at 120, the leap check removed, every
February given a 29th, the candidates tried oldest first, the range gate
removed, the readability gate removed, the width gate removed, the type gate
removed, `MAX_BIRTH_AGE` as 100, the century hard-coded to 2000, the two
printed year digits read as the day, and the reference-date type check removed.

Verified: `python -m pytest backend/tests/unit/test_mrz.py -q` reports `376
passed` (330 before this task's tests), `test_td1.py` `264`, `test_td2.py`
`273`, `test_td3.py` `521`; `python -m pytest backend/tests -q -p
no:faulthandler` reports `1451 passed` (was 1405) and exits 0; **`scripts/
check-all.ps1` exits 0** (1451 backend, 45 frontend, build); `python -m
compileall -q backend` exits 0; importing `mrz` loads neither `cv2` nor
`numpy`, so Gate 1 holds. Scope was `mrz.py`, `test_mrz.py`, the `tasks.md`
marker and note, and this handover; no other source file and no `lorebook/`
file was touched, and no writing git command was run. The mutant harness was a
throwaway at the repo root and deleted itself with its restore.

**Task 3.11 -- a date says more than its width: `YYMMDD` is parsed, the month
and the day are range-checked, and `"993199"` and `"013200"` are refused by
name in all three formats.** `mrz.py` gains `MrzDate` (a frozen dataclass of
`year`, `month`, `day`), `parse_date(text) -> MrzDate | None`,
`date_fault(text) -> "month" | "day" | None`, and two documented constants,
`DATE_LENGTH = 6` and `MONTH_DAYS`. All three formats call `date_fault` from
`validate_date_of_birth` and `validate_date_of_expiry` -- six call sites, one
copy of the rule -- and every message names the field, its positions and the
fault, and never the date. `__all__` gains three names (eleven in all).

**The rule lives in `mrz.py` because `YYMMDD` is the one thing all three
formats print the same way, and because "may delegate but may not reimplement"
is a rule this package already enforces.** A TD1, a TD2 and a TD3 refusing
different months would be the quietest possible drift, so
`test_this_module_states_positions_and_computes_nothing` now also asserts
`td2.date_fault is mrz.date_fault`.

**Reading and judging are two functions because they are two questions, and
2.14's three answers become three here.** `parse_date` reads six characters
into three numbers and answers `None` when they are not all ASCII digits;
`date_fault` names the component that could not be a day. **The split is the
task's most load-bearing decision**, because it keeps two findings apart: a
date that could not exist is contradicted by name, while a field of letters or
fillers is *unreadable* and belongs to the check digit printed beside it. So
`"AAAAAA"`, `"<<<<<<"`, `"abcdef"` and `"74o812"` still parse in all three
formats -- refusing them in the reader would throw that finding away and
report an OCR slip as a document nobody could read.

**Two deliberate non-decisions, both stated in the module and pinned by
tests.** **No century is implied anywhere**: `MrzDate.year` is the two
characters the line printed as an `int` in `0`-`99`, `"000101"` and `"000229"`
are accepted, and 3.12 and 3.13 can still be asked which century each of the
two dates means -- a range check that needed a century would have had to
invent one. And **February's entry in `MONTH_DAYS` is 29, not 28**, because a
date carries two digits of year and cannot say whether *this* February had a
29th; 29 is the largest that refuses nothing genuine, and the leap-year
question belongs to 3.12. Flattening every month to 31 would accept more
nonsense and refuse nothing; answering leap years here would need a century
this package has not been given.

**`date_fault` passes a wrong width over rather than judging it, which 2.11
forces rather than anything choosing.** How wide a date is belongs to the
layout table all three validators read it from, and `test_td3.py`'s
`test_each_new_reader_takes_its_positions_from_the_layout_rather_than_its_own`
moves a date field in its table to five characters: a width rule inside `mrz`
would refuse that field for being five wide and fail a test whose whole claim
is that the reader takes its positions from the layout. `parse_date` stays
strict and raises, because a caller holding five characters has made a
mistake; `date_fault` is the one function that does not judge width, and a
removal mutant on that guard fails 8 tests, two of them that pair.

**The whole rule is measured rather than remembered.** One test walks every
one of the fourteen month values (`00` through `13`) against every day from
`00` to `32` -- 462 cases -- against a longhand copy of the maxima written in
the test rather than read from `mrz.MONTH_DAYS`, with the count asserted so
the loop cannot shrink quietly. A second test asserts that the six date
fields in `TD1_LINE_2`, `TD2_LINE_2` and `TD3_LINE_2` are all
`mrz.DATE_LENGTH` wide, resolved from the package so a fourth format is
covered by being added.

**Five mutants were run against the suite and all five are caught** --
`str.isdigit()` in place of the ASCII digit test (caught by the single
non-ASCII-digit row, which is why that row is there), February at 28 (5
tests), the width guard removed (8 tests), `YYMMDD` read as `YDMY` (168 tests,
because the specimen's own `"740812"` becomes month 74), and one format's
`date_fault` call deleted (5 tests). **The non-ASCII row is the one that
needed writing rather than remembering**: `str.isdigit()` answers `True` for
`"?"` and `int()` accepts it, so the obvious way to test for digits parses an
Urdu-Indic zero into a date.

Verified: `python -m pytest backend/tests/unit/test_mrz.py -q` reports `330
passed` (285 before this task's tests), `test_td1.py` `264`, `test_td2.py`
`273`, `test_td3.py` `521`; `python -m pytest backend/tests -q -p no:faulthandler`
reports `1405 passed` (was 1327) and exits 0; **`scripts/check-all.ps1` exits
0** (1405 backend, 45 frontend, build); `python -m compileall -q backend` exits
0; importing `td1`, `td2` and `td3` loads neither `cv2` nor `numpy`, so Gate 1
holds. Scope was `mrz.py`, `td1.py`, `td2.py`, `td3.py`, the four test files,
the `tasks.md` marker and note, and this handover; no other source file and no
`lorebook/` file was touched, and no writing git command was run.

**Task 3.10 -- TD2 line 2 is parsed, the composite's span is settled, and the
specimen's two remaining printed digits are derived rather than trusted.**
`td2.py` gains six `parse_`/`validate_` pairs (document number, nationality,
date of birth, sex, date of expiry, optional data), a closed
`TD2_SEX_MARKERS`, `parse_td2_line_2` (eleven fields in printed order inside
a read-only `MappingProxyType`), `TD2_COMPOSITE_SPANS`,
`TD2_CHECK_DIGIT_FIELDS`, `td2_composite_input` and
`td2_check_digit_results`. Fourteen names added to `__all__`, twenty-eight in
all.

**The task's own field list was a TD1's and is corrected, the way 3.9
corrected its own.**  It said "DOB, sex, expiry, nationality, optional data,
final composite"; a TD2's line 2 opens with the **document number and its own
digit at 1-10**, then nationality, date of birth and its digit, sex, date of
expiry and its digit, six characters of optional data, that field's digit and
the composite.  `TD2_LINE_2` was pinned by 3.8, so the correction is settled
against the table.

**The composite's span is settled here, and it is not the span the task text
stated -- for the reason 3.7 settled one in `td1.py`.**  The text's three line
2 spans (1-7, 9-15, 19-29) are `TD1_COMPOSITE_SPANS`'s line 2 spans
**verbatim**: applied to a TD2 they cut the document number, the date of birth
and the optional data, and take in the nationality and the sex marker -- the
two fields no composite in this package reaches.  Its line 1 portion ("6-30")
stops five characters into a 31-character name, which nothing in the format's
shape explains.  **What the shape does say:** the span includes every check
digit the line prints (10, 20, 28, 35), skips the nationality at 11-13 and
the sex marker at 21 as both siblings' spans do, and on line 1 reaches the
**name at 6-36 whole**, the only field of that line any digit can reach.
`TD2_COMPOSITE_SPANS` is therefore **62 characters, 31 from each line, and it
is the TD3's own composite with the name in front of it and the last eight
positions of line 2 dropped** (1-10, 14-20, 22-35 against 1-10, 14-20,
22-43) -- a structural claim a test asserts against `td3.py` rather than
prose stating.  **This repository still holds no copy of Doc 9303**, so the
span is the standard's as this project states it and a sourced copy of Part 7
is the only thing that would make it a lookup.  **It is the one claim in this
module with no second source behind it, and it is the load-bearing one: get it
wrong and every genuine visa's composite row fails.**

**The specimen's five printed digits: three quoted and confirmed, two derived
-- 1.6's rule applied rather than avoided.**  The line is the same fictitious
visa line 1 quotes, with the standard's own document number "L898902C<"
(eight characters and a filler, so the padding rule has a *value* on the
specimen) and its personal number cut from a TD3's fourteen characters to this
format's six.  The "3" at 10, the "2" at 20 and the "9" at 28 are the digits
the same three fields print on the TD1 and TD3 specimens, and each is checked
against `mrz.check_digit` in a test.  **The optional data's own digit ("8")
and the composite ("3") are computed and written in**, so a green composite row
is a claim about this project and never about any visa.

**A correct specimen gives five `True` rows and no `None`, the one thing this
format's specimen does not share with the TD1's**, because this optional data
is filled in.  The unused case is tested rather than assumed: six fillers with
the filler in the digit position give `found 0, expected None, passed None`,
and with that row unable to say "failed" the composite is the only row that can
see an edit to the field.

**A line 1 handed to the line 2 assembler is not caught, and that is now a
test rather than a surprise.**  Positions 1-9 are "V<UTOERIK" (not filler, so
a short padded number), 11-13 are "SON" -- an MRZ prints a name in capitals,
so three uppercase letters -- and 21 is an "M", so the parse *succeeds*.  What
it does not do is accuse the document: every printed digit position on a line 1
holds a letter or the filler, so all five rows come back "could not be read"
rather than "failed".  Two docstrings that had claimed the nationality would
catch it are corrected.

**3.9's padding is load-bearing in fact now**: the name is inside the span, so
a filler changed in its padding moves the composite and nothing else.  The
test picks a character that moves it -- a filler printed as "A" is worth zero,
exactly as the filler is, which is 2.14's blind spot one field along.

**Three existing tests were rewritten rather than deleted**, each because the
claim it stated was no longer the true one: the "computes nothing" test (the
banned list relaxes by one name -- `check_digit_results` -- now that this
module delegates to it, and gains the positive `td2.check_digit_results is
mrz.check_digit_results`), the "holds no composite span" test (absence becomes
single authorship), and the assembler/validator test (parametrised over both
lines, with line 2's five printed digits deliberately absent from the list,
because a count of eleven would claim the parse judges digits).

Verified: `python -m pytest backend/tests/unit/test_td2.py -q` reports `265
passed` (was 121); `python -m pytest backend/tests -q -p no:faulthandler`
reports `1327 passed` (was 1183) and exits 0; **`scripts/check-all.ps1` exits
0** (1327 backend, 45 frontend, build); `python -m compileall -q backend` exits
0; importing `app.pipeline.tier0.td2` loads neither `cv2` nor `numpy`, so Gate
1 holds.  **Eighteen mutants were run against the suite and all eighteen are
caught** -- the span's four runs each moved (including the task text's own
6-30, its 1-7, and one taking the composite), the nationality and the sex
marker swallowed into the span, the spans transposed and reordered, the
optional data widened to fourteen, the sex set widened, the document number
accepting an all-filler field, the optional data stripped, the assembler
reading a field raw, the composite input skipping the width check, the pairings
reordered, and the two messages that must not echo their value.  Scope was
`td2.py`, `test_td2.py`, the `tasks.md` marker and note, and this handover; no
other source file and no `lorebook/` file was touched, and no writing git
command was run.

**Task 3.9 -- TD2 line 1 is parsed, and the task's own field list was a TD1's: line 1 is the document header and the holder's name.**  `td2.py` gains `td2_field` (the one place a TD2 line is sliced), a closed `TD2_DOCUMENT_CODES` (`{"V<", "V"}`), three `parse_`/`validate_` pairs -- document code, issuing state, **name** -- and `parse_td2_line_1`, which returns all three fields of line 1 keyed by name in printed order inside a read-only `MappingProxyType`.  Nine names in `__all__` (fourteen in all), and `test_the_layout_names_are_exported` also asserts that **no** composite and **no** `parse_td2_line_2` is exported, so 3.10's two decisions cannot be inherited by importing a name that already exists.

**The task text said "document code, issuing state, document number, optional data with its own check digit", and that is `TD1_LINE_1` verbatim.**  In a TD2 the document number and its digit are at 1-10 of **line 2** and the optional data at 29-35 of line 2, and line 1 holds the **name** at 6-36 -- the field a visa MRZ most visibly carries, and the one 3.9 and 3.10 between them named nowhere.  `td2.py` parses the standard's line, `tasks.md` 3.9's list is corrected to match, and `test_the_document_number_and_the_optional_data_are_line_2_fields` keeps the correction honest.  **3.10's list is wrong in the same way and is not edited here** -- it is 3.10's own correction, and its composite span is still 3.10's question against the standard.

**A specimen is a remembered check digit, so 3.9 is the task 1.6 pointed at -- and on this line the objection does not arise, for a reason that is the format's shape rather than anybody's care.**  **A TD2 line 1 prints no check digit at all**, so the sample visa's first line carries no printed digit to take on trust.  What cannot be confirmed is the *name*, and no arithmetic in this project computes over a name, so nothing this project will later report rests on the fixture.  The one thing that *is* checked about it is the one thing this project can check: every character on the line is one `mrz.CHAR_VALUES` prints, which catches a misremembered line that no check digit would have caught.  The specimen is `V<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<` -- 36 characters, 31 of them name: a surname, the `<<` that divides it from the given names, and eleven fillers.  **3.10 is the task where that stops being true**, because line 2 prints five digits and 3.10 is where the span they are computed over has to be settled.

**The name is extracted and judged for its width and nothing else**, which is `td3.py`'s rule carried over rather than a new one: the standard fixes where the name sits and how wide it is, and nothing about the characters, so a diacritic, a lower-case read or a space where a `<<` belongs is a misread a flag wants to point at rather than a reason to drop the visa.  **The padding is returned with it**, because if 3.10's composite covers any part of this line then a stripped filler would change the digit 3.10 computes -- and the name is 31 characters where a TD3's is 39, a width difference the tests state as a comparison against `td3.py` rather than as a number.  **Its message names the positions and the two lengths and never the name**: the one field on this line that is a person rather than a document.

**What tells a TD2's two lines apart is two fields and not one, and the asymmetry is now a test.**  The document code refuses a line 2 whose number does not start `V<`, and the test says so on its first two characters.  But a number that *does* start `V<` reaches the code reader as a perfectly good visa code, because a document number is filler-padded on the right and may be as short as an authority likes; positions 3-5 are then the third through fifth characters of a number, so the **issuing state** is what catches it.  Two rules, two fields, neither of them a check digit, since this line prints none.

**The document code's message echoes what it found, and the cost of that is written down rather than left to be discovered.**  `td1.py`'s exception is that two characters in the code position describe a *document*; on a TD2 the same two characters are the first two of a holder's document number whenever the caller handed over the wrong line.  The echo stays -- the caller has the whole line in hand already, the message is what tells an operator the zone was read as the wrong format, and a message naming only what was expected would cost the diagnosis to protect two characters from a log line that would have held forty-four of them.

**Sixteen mutants were run against the suite and all sixteen are caught.**  Two of them first went uncaught and are what `test_the_assembler_hands_every_field_to_its_validator` exists for: an assembler that reads a field raw instead of handing it to its validator is **equivalent** on a well-formed line, because the width gate has already run and the slice is 31 characters either way -- so equivalence needed a test rather than a demonstration, and that test now counts all three validators beside the three reads.  Two existing tests were rewritten rather than deleted, which 3.8's own note said the first of them would have to be: `test_this_module_states_positions_and_computes_nothing` (its "defines no function at all" assertion became 3.3's and 3.7's per-function "computes nothing" loop) and `test_this_module_defines_no_error_type_of_its_own` (absence became identity -- the class in `vars(td2)` is `mrz.MrzValueError`, the same object, because importing it put mrz's class in the namespace without this module ever having defined one).

Verified: `python -m pytest backend/tests/unit/test_td2.py -q` reports `121 passed` (was 42); `python -m pytest backend/tests -q -p no:faulthandler` reports `1183 passed` (was 1104) and exits 0; **`scripts/check-all.ps1` exits 0** (1183 backend, 45 frontend, build); `python -m compileall -q backend` exits 0; importing `app.pipeline.tier0.td2` loads neither `cv2` nor `numpy`, so Gate 1 holds.  Scope was `td2.py`, `test_td2.py`, the `tasks.md` marker and note, and this handover; no other source file and no `lorebook/` file was touched, and no writing git command was run.

**Task 3.8 -- the TD2 layout exists as two tables of 36 positions, with a
coverage test that accounts for every position of every line, and no reader,
no span and no specimen.** New `backend/app/pipeline/tier0/td2.py`:
`TD2_LINE_LENGTH = 36`, `TD2_LINE_COUNT = 2`, `TD2_LINE_1` (3 fields),
`TD2_LINE_2` (11 fields) and the `TD2` aggregate holding those *same dict
objects*, `__all__` exactly those five names. Line 1 is `document_code` 1-2,
`issuing_state` 3-5 and `name` 6-36; line 2 is `document_number` 1-9 and its
digit 10, `nationality` 11-13, `date_of_birth` 14-19 and its digit 20, `sex`
21, `date_of_expiry` 22-27 and its digit 28, `optional_data` 29-34 and its
digit 35, `composite_check_digit` 36. `__all__` holding five names is the
scope assertion, not a formality: a sixth name would be a reader, a span or a
digit arriving before the task that owns it, and a test says so.

**The format is a TD3's shape at 36 characters a line, and the whole of the
8-character difference is the optional data.** Line 1 is header plus name as
in a TD3, and line 2's first 28 positions are the same fields, in the same
order, at the same positions as a TD3's line 2 -- a test asserts that against
`td3.py` rather than asserting it in prose -- and then the formats part: a
TD3 spends 16 positions on a personal number, its digit and the composite
where a TD2 spends 8 on an optional data field, **its own check digit** and
the composite. So a TD2's optional data is 6 characters wide, not 14, and
that is the number most likely to arrive wrong from memory. **Five check
digits are printed and all five are on line 2**, where a TD1 prints five
across two lines; line 1 carries none, so its last position is the last
filler of the name and a reader pointed at the wrong line here gets a name
with nothing underneath it objecting.

**36 is the first line length the digits and the letters fill exactly**, so
the synthetic line is `string.digits + string.ascii_uppercase` with nothing
to spare and position 36 is `Z`; every expected slice is written longhand,
which is what makes a boundary one character out fail on a value rather than
passing as self-consistent. The named test is
`test_a_line_covers_positions_1_to_36_with_no_gap_or_overlap`, parametrised
over both lines and stated three ways as 3.4 stated its twin. Six position
mutants were run against the suite -- the optional data one position late,
the document code one late, the name one early, the optional data's digit
moved onto the composite, the sex marker one late, and an inverted composite
span -- and each fails 5 to 8 tests.

**`tasks.md` 3.9 and 3.10 describe the TD1's field distribution rather than a
TD2's, and this task records that rather than editing them.** 3.9 lists TD2
line 1 as "document code, issuing state, document number, optional data with
its own check digit" and 3.10 lists TD2 line 2 as "DOB, sex, expiry,
nationality, optional data, final composite". Between them they name no field
for the holder's name -- which is a visa MRZ's most visible field and the
only thing a TD2 line 1 holds besides the header -- and 3.10's composite span
(line 1 6-30 plus line 2 1-7, 9-15 and 19-29) is `TD1_COMPOSITE_SPANS` with
the line 1 portion left in place. **Those three line 2 spans are the TD1's
verbatim, and applied to a TD2 they would put the composite over the sex
marker and the nationality, which no other composite in this package does.**
`td2.py` therefore publishes no span constant, and
`test_this_module_holds_no_composite_span` asserts there is none, so the
wrong span cannot be inherited by importing a name that already exists --
which is exactly how 3.5's wrong TD1 span survived into 3.6. 3.9 and 3.10
have to settle the field distribution and the span against the standard, the
way 3.7 did.

**No specimen MRZ, on 3.4's reason.** Quoting a visa specimen means quoting
printed check digits this project has not verified, which is 1.6's refusal
for a TD3 composite and 3.4's refusal for a TD1; 3.9 is the task that brings
a printed visa into reach. **And this repository holds no copy of Doc 9303,
so these positions are stated as the standard states them rather than as a
list something here could look up** -- the same caveat `td1.py` and
`test_td3.py` carry, written into the module at the moment the claim is made
because 3.5's span was written down unchecked, carried forward by 3.6, and
found wrong by 3.7.

Verified: `python -m pytest backend/tests/unit/test_td2.py -q` reports `42
passed`; `python -m pytest backend/tests -q -p no:faulthandler` reports `1104
passed` (was 1062) and exits 0; **`scripts/check-all.ps1` exits 0** (1104
backend, 45 frontend, build); `python -m compileall -q backend` exits 0;
importing `app.pipeline.tier0.td2` loads neither `cv2` nor `numpy`, so Gate 1
holds. Scope was `td2.py`, `test_td2.py`, the `tasks.md` marker and note, and
this handover; no other source file and no `lorebook/` file was touched, and
no writing git command was run.

**Task 3.7 -- the TD1 composite is built and verified, and the span 3.5
flagged as unchecked is settled: `tasks.md` was right and `td1.py` was
wrong.**  `td1.py` gains `TD1_COMPOSITE_SPANS` (line 1 1-10 and 15-30, line 2
1-7, 9-15 and 19-29 -- 51 characters, 26 from line 1 and 25 from line 2),
`TD1_CHECK_DIGIT_FIELDS`, `td1_composite_input(line_1, line_2)` and
`td1_check_digit_results(line_1, line_2, sources)`, which hands
`mrz.check_digit_results` its own list of five rows exactly the way
`td3_check_digit_results` does.  The specimen's printed composite now agrees
with those 51 characters, and a mutated one fails the composite row and
nothing else over all nine wrong digits.

**The three arguments that settle the span are about the format's shape, not
about a document, which is why they are recorded rather than a citation.**
The span *starts* at line 1 position 1, so it covers the document code and the
issuing state -- the two fields no printed check digit in a TD1 reaches.  It
*includes every check digit line 1 prints*, positions 15 and 30, which is the
rule `td1.py`'s old span broke by leaving line 1's own last position out; a
TD3's composite covers that format's four check digits at 10, 20, 28 and 43,
and `tasks.md` 3.10 states the same for a TD2, so dropping one would make this
format the odd one out in the package.  And it reads line 2 the way both other
formats read theirs: the date of birth and its digit, the expiry and its
digit, the optional data -- skipping the sex marker at 8, the nationality at
16-18 and its own position.  **This repository still holds no copy of Doc
9303**, so the span is stated as the standard states it rather than as a list
something here looked up, with the same standing caveat 3.6 attached to
`TD1_SEX_MARKERS`.

**The spans are positions on a named line, and that is forced rather than
chosen: line 1 1-10 stops five characters into the nine-character document
number, so no list of whole field names can name it.**  This is the one place
`td1.py` departs from `td3.py`'s `TD3_COMPOSITE_FIELDS`, and it is a real
consequence rather than a second convention -- which makes the document
number's *last four characters* the one part of a TD1 that no composite covers.
Editing them fails the number's own row and nothing else, and that is now a
test rather than a surprise.  Every other span in the composite is a run of
whole fields, and a test asserts the one cut is the document number and
nothing else, which is what makes a span one position out fail on a value.
Six span mutants were run against the suite -- the old 6-14/16-29, one
position early, one late, the two spans transposed, line 2's sex marker pulled
in, and line 1's own digit dropped -- and each fails 9 to 13 tests.

**The one existing value this task changed is the specimen's composite digit,
and it is the second time a remembered check digit has been checked and found
to be wrong.**  3.6 wrote `"6"` at line 2 position 30 from memory, with a test
named `test_the_composite_is_carried_as_printed_and_verified_by_nothing`.
3.7 computed the standard's 51 characters and got **`7`**; the old span also
comes to 7, and no plausible reading of either line produces 6.  The
remembered digit was therefore one of the two values 1.6 refused to state, and
the choice `test_td3.py` made for its own composite was made here:
`SPECIMEN_LINE_2` now carries `7`, the tests pin the *span* longhand rather
than a published character, and the fixture is the arithmetic's rather than a
document's.  **The green result proves the 51 characters the standard names,
the digit the line prints and the verdict over them are one story -- and says
nothing about whether 7 is the character any real card carries**, exactly as
1.6 recorded for the TD3.  The 3.6 test keeps its second half, which was
always the point: the parse still carries the digit and still judges none of
them.

**A correct specimen yields four `True` rows and one `None`, and the `None` is
a property of the format rather than of the fixture.**  Optional data 1 is
fourteen fillers, so its check digit position prints filler rather than a
digit: `found 0, expected None, passed None`.  3.3's three-way answer is doing
real work here for the first time on an unmutated card, because a `False`
would be 2.14's mistake on the strength of a field nobody filled in.  The
same property cuts the other way, and that is asserted too: with that field's
own row unable to say "failed", the **composite is the only row on the card
that can catch an edit to it**.

**`td1_composite_input` checks both lines' widths through the existing
`_checked_line`, which `td3.py` does not need and this format does.**  A TD3
caller who skipped the zone gate got a short *field*; a TD1 caller who skipped
it would get a silently short 51-character span, which comes back as a
composite that *failed* rather than as an error.  That is the one failure
mode a caller could not tell from a forged document, and the check costs
nothing twice because both parsers already make it.

Verified: `python -m pytest backend/tests/unit/test_td1.py -q` reports `250
passed` (was 225); `python -m pytest backend/tests -q -p no:faulthandler`
reports `1062 passed` (was 1037) and exits 0; **`scripts/check-all.ps1` exits
0** (1062 backend, 45 frontend, build); `python -m compileall -q backend`
exits 0; importing `app.pipeline.tier0.td1` loads neither `cv2` nor `numpy`,
so Gate 1 holds. The `__all__` pin carries all thirty-three names, and
`test_this_module_states_positions_and_computes_nothing` was rewritten the way
3.3 rewrote `td3.py`'s twin -- the `banned in vars(td1)` loop stays, and
`td1.check_digit_results is mrz.check_digit_results` is the assertion that
delegation and duplication are different things. Scope was `td1.py`,
`test_td1.py`, the `tasks.md` marker, the 3.4/3.5/3.6 notes that stated the
span the other way round, and this handover.

**Task 3.6 -- TD1 line 2 is parsed, and the specimen's second printed digits
are verified rather than trusted.** `td1.py` gains `TD1_SEX_MARKERS`, five
`parse_`/`validate_` pairs (date of birth, sex, date of expiry, nationality,
optional data 2) and `parse_td1_line_2`, the twin of `parse_td1_line_1`: all
eight fields of line 2, keyed by name in printed order, inside a read-only
`MappingProxyType`. **The specimen is the same ICAO 9303 Part 4 sample ID
card**, and its line 2, `"7408122F1204159UTO<<<<<<<<<<<6"`, is quoted with
both its printed digits *checked*: `mrz.check_digit("740812")` is the `2` at
position 7 and `mrz.check_digit("120415")` is the `9` at position 15. That is
the gap 3.5 closed for line 1, closed here for the two dates, and it is what
lets 1.6's rule be honoured a second time.

**Both decisions the handover named were made, and neither was inherited.**
The **dates** are judged for their width and for nothing else, because
`YYMMDD` range validation is 3.11's: `"993199"`, `"013200"`, `"AAAAAA"` and
`"<<<<<<"` are all accepted today, exactly as printable as `"740812"`. A
reader that refused an impossible month would not merely duplicate 3.11 --
it would make it unreachable, since the line would be reported as unreadable
rather than as carrying a bad month, and the flag that wants to say so would
have nothing left to read. The **sex marker** is a closed set of four,
`{"M", "F", "X", "<"}`, the same four `TD3_SEX_MARKERS` holds. Line 2's
position 8 is the one field on the line no digit in this project covers --
the composite skips it, and neither date's own digit reaches it -- so a rule
such as "one uppercase letter, or the filler" would wave `N` and `Q` through
with nothing anywhere to object.

**3.11 has since made the second half of that decision true.** The month
and the day are judged: `"993199"` is refused and `"AAAAAA"` is still
accepted, for the reason the paragraph above gives.

**The sex set is a decision taken against a missing source, and that is
stated rather than hidden.** This repository holds no copy of Doc 9303, so
`TD1_SEX_MARKERS` is the TD1 table's set as this project states it, not a
list anything here checked. The two errors are not symmetric, and the set
goes against the cheaper one: dropping `"X"` refuses a card that is
well-formed, which is exactly the failure a nationality code list with one
country missing produces and the one `validate_issuing_state` already refuses
to make by shipping no list at all; keeping `"X"` accepts a marker no card may
print, in a field only a rules engine (Part 12) can flag. **If the table reads
`M`, `F` or `<` alone, dropping `"X"` is a one-character edit and nothing else
in this module moves.**

**Three printed digits on this line are carried and judged by nothing** --
positions 7, 15 and 30 -- which is 2.4's rule and 3.7's question, the same
deferral line 1's two digits already answer by. The composite is carried as
the `"6"` the document printed and is **not** compared against any computed
span, because that span is still unsettled: `td1.py` says line 1 6-14 and
16-29 and `tasks.md` 3.7 says line 1 1-10 and 15-30. A mutated composite
parses, and a test says so.

**A line 1 read as a line 2 is caught by the sex marker and not by the
dates, and that asymmetry is now a test rather than a hope.** Line 1's
positions 1-6 are `"I<UTOD"` -- six characters of the right width that
`validate_date_of_birth` accepts, because what a date may print is 3.11's
question -- and position 8 is a digit of the document number, so the
refusal comes from the one field with a closed set. The other direction
stays 3.5's issuing-state test. A nationality read off line 3 is still
accepted (three uppercase letters out of a holder's name), because the
composite skips positions 16-18 exactly as it skips the sex marker: that
field's plausibility is the rules engine's question, not a check digit's.

**The line-width check moved into a private `_checked_line`, and one 3.5
test changed on purpose.** The two assemblers now share one width check and
one message rather than each writing its own, so the zone gate that will
cover all three lines takes it over once instead of one assembler being left
behind; the message is unchanged, so nothing a caller was told before is
contradicted. `test_a_line_2_cannot_be_mistaken_for_a_line_1` had its own
local copy of the line 2 literal, which is now the module-level
`SPECIMEN_LINE_2`, so the specimen is quoted once. No other 3.5 test moved,
and the exported-name pin carries all twenty-nine names.

Verified: `python -m pytest backend/tests/unit/test_td1.py -q` reports `225
passed` (was 129); `python -m pytest backend/tests -q -p no:faulthandler`
reports `1037 passed` (was 941) and exits 0; **`scripts/check-all.ps1` exits
0** (1037 backend, 45 frontend, build); `python -m compileall -q backend`
exits 0; importing `app.pipeline.tier0.td1` loads neither `cv2` nor
`numpy`, so Gate 1 holds. Scope was `td1.py`, `test_td1.py`, the `tasks.md`
marker and note, and this handover.

**Task 3.5 -- TD1 line 1 is parsed, and for the first time in this format
against printed characters rather than against a table.** `td1.py` gains
`td1_field` (the one place a TD1 line is sliced, the TD3 twin of
`td3_field`), the closed set `TD1_DOCUMENT_CODES` (`{"I<", "I"}`), four
`parse_`/`validate_` pairs -- document code, issuing state, document number,
optional data 1 -- and `parse_td1_line_1`, which returns all six fields of
line 1 keyed by name in printed order inside a read-only `MappingProxyType`.
**The specimen is the ICAO 9303 Part 4 sample ID card's line 1,
`"I<UTOD231458907<<<<<<<<<<<<<<<"`, and the one printed digit it carries is
verified rather than trusted:** `mrz.check_digit("D23145890")` is the `7` at
position 15. That is the gap 3.4 named -- a specimen whose check digit nobody
has checked is a remembered value, and 1.6 refused to quote one -- and it is
now closed for line 1, which is all this task reads.

**Two printed digits are carried and judged by nothing.** Positions 15 and 30
come back as the characters the document printed, filler included, because
whether they agree is 3.7's question. A line whose position 15 disagrees with
its own arithmetic still parses, and a test says so: reading a document is
not verifying one, and a parse that refused the line would have thrown the
finding away. Every other field comes back exactly as printed too, because
those two digits are computed over the characters as they stand.

**Optional data 1 is judged for its width and for nothing else, which is
2.4's rule applied a second time.** "Filler only means unused" is not a rule
the standard states, so the specimen's fourteen fillers come back as fourteen
fillers rather than as an empty string a caller would have to interpret, and a
space inside the field comes back untouched for 3.7's arithmetic to object
to.

**The assembler checks the line's width, and that is new: with no zone gate
yet, a 29-character line sliced its last field to an empty string and reported
the rest of the line as a document, quietly losing a position.** The gate
that will cover all three lines takes the check over rather than it being
repeated in two places; 3.4's promise that the shape gate is "a later task
again" is about the *zone*, and this is the one line.

**No record type is created, deliberately.** `parse_td3` returns the frozen
`MrzDocument`, and 3.14 is where that becomes the common currency with a
`format` discriminator; a TD1 record invented now would be a second shape for
3.14 to merge. A mapping keyed by the layout's own field names is the shape
that survives that merge, and it is read-only for `MrzDocument.sources`'
reason -- the evidence of what the document printed must not be editable.

**The composite is not asserted anywhere, and 3.7 is blocked on a question
rather than on work.** This module's docstring says the composite is computed
over line 1's 6-14 and 16-29, excluding the document number's own digit at
15; `tasks.md` 3.7 says "line 1 positions 1-10 and 15-30", which covers the
document code and the issuing state and *includes* 15. The two differ exactly
where the specimen prints its `7`. **Neither span has been checked against
the standard text**, and the filler's value of `0` means the difference is
not cosmetic: it decides whether `D` and `7` are inside the arithmetic at
all. So the specimen's printed composite is not quoted, no test computes a
span, and the conflict is recorded in `td1.py`'s docstring rather than
settled in either direction. 3.4's handover asserted that `td1.py` had the
standard's spans and `tasks.md` the wrong ones; that was a claim about a
document neither of us had open, and this task takes it back. 3.7 has to
settle it against the standard, not against the other source.

Verified: `python -m pytest backend/tests/unit/test_td1.py -q` reports `129
passed` (was 42); `python -m pytest backend/tests -q -p no:faulthandler`
reports `941 passed` (was 854) and exits 0; **`scripts/check-all.ps1` exits
0** (941 backend, 45 frontend, build); `python -m compileall -q backend` exits
0; importing `app.pipeline.tier0.td1` loads neither `cv2` nor `numpy`, so
Gate 1 holds. Scope was `td1.py`, `test_td1.py`, the `tasks.md` marker and
note, and this handover. The 3.4 tests are untouched apart from the
`__all__` pin, which now carries all seventeen names, and the module
docstring's paragraph that said "there is no specimen here".

**Task 3.4 -- the TD1 layout exists as three tables of 30 positions, with a
coverage test that accounts for every position of every line.** New
`backend/app/pipeline/tier0/td1.py`: `TD1_LINE_LENGTH = 30`,
`TD1_LINE_COUNT = 3`, `TD1_LINE_1` (6 fields), `TD1_LINE_2` (8),
`TD1_LINE_3` (`name` alone, 1-30) and the `TD1` aggregate holding those
*same dict objects*, `__all__` exactly those six names. Nothing else -- no
reader, no shape gate, no arithmetic. The named test is
`test_a_line_covers_positions_1_to_30_with_no_gap_or_overlap`, parametrised
over all three lines: it collects every span in a table and asserts
`sorted(claimed) == list(range(1, 31))`, stated three ways (the sorted
comparison, a per-boundary adjacency check, and the slices rebuilt into the
whole line) because counting to 30 would not catch a gap that an overlap
cancels out.

**A new module per format, following `td3.py` and not `ROADMAP.md`'s B1.3
line, which still says `mrz.py` and `tests/test_mrz_td1.py`.** That roadmap
line is the stale half of a split that happened during Part 2; `td1.py` and
`test_td1.py` are the pattern 3.3's handover pointed at.

**No specimen MRZ, deliberately.** Quoting a TD1 specimen means quoting a
printed check digit this project has not verified, which is what 1.6 declined
for the TD3 composite; 3.5 is the task that brings one into reach. So the
positions are checked against a synthetic 30-character line whose characters
name the positions they stand in, and each of the 15 expected slices is
written longhand from the standard. That second copy earned its keep
immediately: my `optional_data_1` expectation was one character too long and
the test failed on the value rather than passing as self-consistent.
`test_mrz.py`'s package scan globs `tier0/*.py`, so its "one error type" and
"never raises a builtin" invariants now cover `td1.py` with no edit needed.

Verified: `python -m pytest backend/tests/unit/test_td1.py -q` reports `42
passed`; `python -m pytest backend/tests -q -p no:faulthandler` reports `854
passed` (was 812) and exits 0; **`scripts/check-all.ps1` exits 0** (854
backend, 45 frontend, build); `python -m compileall -q backend` exits 0;
importing `app.pipeline.tier0.td1` loads neither `cv2` nor `numpy`, so Gate 1
holds. Scope was `td1.py`, `test_td1.py`, the `tasks.md` marker and note, and
this handover.

**Task 3.3 -- `MrzDocument` now carries the five check-digit verdicts, and the
verdict is a three-way answer rather than a boolean.** New
`check_digit_results: tuple[CheckDigitResult, ...]` on the record, declared
immediately after `composite_check_digit` and populated by `parse_td3`; five
rows in printed order (`document_number`, `date_of_birth`, `date_of_expiry`,
`personal_number`, `composite`), each naming its field and carrying `expected`
and `found` as `int`. **`mrz.py` gains `CheckDigitResult` and
`check_digit_results`** -- the arithmetic stays there, and `td3.py` gains only
the five pairings (`TD3_CHECK_DIGIT_FIELDS`) and the composition
(`td3_check_digit_results`), which reads the four field pairs out of `sources`
and takes the composite's characters from `td3_composite_input` so there is
still exactly one assembler.

**The design decision, and the reason two Part 2 tests failed on the first
version.** The first implementation made the parse *raise* when a field could
not be read, because `mrz.verify_check_digit` raises and 2.14's rule is that a
`False` would be a forged-document claim the document did not earn. That is
right for one isolated field and wrong for a list, and the suite said so at
once: 2.4's *the personal number is carried as printed and judged by nothing*
(a space in the optional data), 2.12's *only the name is cleaned and a date
comes back exactly as printed* (`"7a0812"` as a date of birth), and *a zone
given the other way round is rejected* (which began reporting
`expected check digit must be a digit 0-9: 'S'` instead of the document
code's own message) all broke. The reason is structural, not a detail: the
composite spans 22 positions, so a single space anywhere in them makes the
whole thing uncomputable, and a list that refused to be built would take the
other four verdicts and the document down with it. **So an unreadable half is
`None`, `passed is None`, and the row is still there** -- with its readable
half still reported, because `expected 2, found unreadable` is what a flag
wants and raising would have thrown the finding away. 2.14's principle is
kept; it is just applied at the level a list lives at. What still raises is a
mistake in the *call*: a non-iterable, an entry that is not a triple, a field
named with something other than a string.

**2.2's guard was rewritten rather than satisfied, and that is the one place
this task changed an existing test on purpose.**
`test_this_module_computes_no_check_digit_of_its_own` asserted `check_digit`
and `verify_check_digit` were not in `vars(td3)` -- still true, but a name
check cannot survive the delegation `td3_check_digit_results` needs. Both
assertions are kept and the rule they stood for is now stated directly:
`WEIGHT_CYCLE` and `CHAR_VALUES` are absent, the new function's source has no
`%`, and `td3.check_digit_results is mrz.check_digit_results` -- the *same
object*, so the sum, the weights and the modulo exist in exactly one place in
the package. The module docstring's "holds no arithmetic" now means
arithmetic rather than reachability.

**The task's two named tests, and what they actually prove.** The specimen
yields five rows in printed order, all `passed is True`, and each mutation of
the four fields -- with the printed digit left exactly where the specimen
printed it -- fails **exactly two rows: the field and the composite**. That is
the standard's three spans rather than a property of the four mutations, and
the contrast is 3.2's forged final digit, which fails the composite row alone.
`test_each_result_is_computed_over_the_characters_its_own_field_holds` pins
the characters per row against longhand expectations and uses the whole of
line 2 -- which comes to `0`, not `6` -- as the near miss. **1.6's limit on
the specimen's digits is unchanged by moving the comparison here:** a green
row means "this line agrees with itself over the characters it printed", never
"this passport is genuine", and the test says so in its own comment.

Verified: `python -m pytest backend/tests/unit/test_td3.py -q` reports `510
passed` (was 497); `python -m pytest backend/tests/unit/test_mrz.py -q`
reports `285 passed` (was 271); `python -m pytest backend/tests -q -p
no:faulthandler` reports `812 passed` (was 785) and exits 0; **`scripts/
check-all.ps1` exits 0** (812 backend, 45 frontend, build); `python -m
compileall -q backend` exits 0; importing `app.pipeline.tier0.td3` loads
neither `cv2` nor `numpy`, so Gate 1 holds. Three existing tests were updated
and are listed in the `tasks.md` note; one stale 2.14 comment claiming the
record holds "nowhere a verdict" was corrected. Scope was `mrz.py`, `td3.py`,
`test_mrz.py`, `test_td3.py`, the `tasks.md` marker and note, and this
handover; no other source file and no `lorebook/` file was touched, and no
writing git command was run.

### Current State & Key Decisions

- **A line is closed by the running maximum of its members' lower edges, and
  the edge is half-open.** A blob joins the line above it while its top is
  *strictly* above that line's deepest member; a blob whose top sits exactly on
  the edge shares no row with it and opens a new line. That is
  `MrzComponent.bbox`'s own convention, and it makes the boundary decidable
  rather than a matter of taste. **Do not compare against the previous blob**:
  it reads the same on a tidy page and cuts a real line in half as soon as one
  glyph hangs below its neighbours, and it fails silently, because both halves
  go on to look like glyphs. Measured on the fixture: the two lines are rows
  105-120 and 175-190, with 55 rows between them against a 15-pixel tallest
  glyph -- which is 4.4's ceiling doing its job.

- **Lines come back down the page and their glyphs come back across it, and
  neither order is 4.3's.** Groups are top to bottom because 4.7 counts them
  and 4.11 maps a cell index to a field offset; members are left to right
  because 4.10 segments along x and cell 0 has to be the leftmost character.
  4.3's `(top, left)` order is the raster-scan order of OpenCV's labelling,
  not the reading order of the document. Do not "preserve" it here: it is the
  order that makes a glyph cell come out in the wrong place.

- **Nothing is filtered, scored or discarded by grouping.** 4.4 owns the band
  and 4.6 owns "is this line plausible"; a line of one comes back as a line
  of one, and the six specks of paper a greyscale frame leaves behind come
  back as two lines of 2 and 4 on the print's own baselines. `area` still
  goes unread, and 4.5 needed no new number of any kind -- the rule is
  relative to the blobs already measured.

- **4.6's answer to "is this line plausible" is two ratios, and a group of one
  passes both.** A line of one has a height spread of zero and no neighbour to
  disagree with, so it comes back -- 4.7's count and 4.10's cell count are
  what judge it, and so are they the answer for the greyscale specks, which is
  the standing correction to 4.5's own note. What 4.6 does refuse is a line
  whose glyphs disagree about their own body size by more than a third of the
  line's median, and a line whose nearest spacing departs from the tightest
  spacing its set shows by more than a quarter of it. `area` still goes unread,
  and neither 4.5's grouping nor 4.6's scores wanted a new number of any kind
  -- both rules are relative to what the previous step already measured.

- **`to_gray` and `binarize_inverted` are the two steps after the rotation, and
  the order is fixed: `deskew`, then `to_gray`, then `binarize_inverted`.**
  4.1 settled the order and 4.2 sits inside it. Both functions are per-pixel or
  per-neighbourhood and **neither changes the grid**, so a region still means
  the same pixel it meant before the rotation. Do not crop, resize or pad
  either one for tidiness: it would offset every polygon 4.8 emits.
- **The cut is local because 4.1 declined to assume the paper was white, and a
  single global cut inherits that assumption straight back.** 4.1 filled the
  new corners with the image's own median for exactly this reason. Measured on
  a page with a one-sided shadow: a global Otsu cut calls 88% of the shadowed
  half ink and gives a 264-pixel component; the local cut calls 2.9% of the
  page, the same as the flat page, and its widest component is one glyph.
  **The honest limit of that claim is now a test**: dimming the whole page
  does *not* need a local cut (everything moves together, so one cut is fine).
  What defeats a single cut is a page that is *uneven*, and only that is
  claimed.
- **The glyphs are the white, and this is not a display choice.** 4.3 numbers
  connected components, 4.4 filters them and 4.5 groups them into lines, and
  all three read ink as "the thing to look at".
  `connectedComponentsWithStats` treats the zero-valued region as background,
  so paper at 0 makes the component list 4.3 reads *be* the glyph list. The
  other way round hands 4.3 one full-page foreground component to reject.
- **`ADAPTIVE_C` is not zero and the reason is arithmetic, not taste.** The
  comparison in `THRESH_BINARY_INV` is "at or below `local mean - C`", so at
  `C = 0` a uniform page compares equal to its own mean and turns entirely
  into ink (84% of the fixture, measured). It also stops grain doing the same
  (40% at 0, 3.0% at 10 on sigma-6 grain). **It is this project's number and
  its risk is stated**: a larger offset buys cleaner paper at the cost of faint
  print, and nothing here can say how far a genuine MRZ stroke sits below the
  paper. Raise it and this helper starts dropping faint print; lower it and
  speckle returns. 4.4's height band is what throws speckle away, so the
  offset is sized to stop the *page* turning white, not to reach a clean
  component list.
- **`ADAPTIVE_BLOCK_SIZE` is a rule, not a tuned optimum, and the rule is
  three constraints the test measures rather than restates.** Odd (OpenCV
  refuses an even neighbourhood), at least twice a glyph, and under a line
  pitch. A sweep of all 26 odd blocks from 11 to 61 shows the reading does not
  move on this fixture, which is *why* the constant is held to the rules. Do
  not retune it to a number that happens to look better on one frame without
  re-running that sweep: the sizes it is checked against are measured from
  the fixture, so 4.14 replacing the generator cannot quietly invalidate the
  rule.
- **`to_gray` is idempotent and that is not what `deskew` does on purpose.**
  `deskew` refuses a one-channel frame because it would run `m7_skew`'s
  estimator on something its author never saw; here the conversion *is* the
  job, so a converted frame is handed straight back, the same object and not a
  copy, exactly as `deskew` reports "nothing was wrong". The conversion is
  **weighted luma, not a channel mean** (red 76, green 150, blue 29; a mean
  says 85 for all three), because a mean puts blue ink and a red security tint
  exactly where black belongs.
- **A three-channel frame handed to `binarize_inverted` is a caller bug, and
  it is left visible.** The two functions are separate so the channel question
  is settled in `to_gray`, where it is known, rather than guessed at in
  `binarize_inverted` where a quiet conversion would hide a mistake in the
  caller behind an answer that looked fine.

- **`m7_skew` owns the skew angle and `mrz_region.deskew` only applies it.**
  `m7_skew.text_skew(image, mode=...)` is the one public signed reading, and
  `assess` calls it in both of its branches, so the quality gate and the
  detector cannot drift onto different estimators. Nothing in
  `mrz_region.py` computes an angle, and two tests hold that: one asserts
  `skew_deg` equals `m7_skew.text_skew`, one replaces `m7_skew`'s reading with
  a sentinel and asserts the rotation follows it.
- **A positive reading is the correction, not the tilt.** A page turned `+5`
  degrees reads about `-5`, and `deskew` rotates by the reading *as it comes*.
  Do not "fix" a sign that looks wrong in a test -- negating it leaves twice
  the tilt, and the test's own readings were taken to find that out.
- **The frame never moves.** Same size, same dtype, same coordinate system as
  the argument, because 4.8's polygons and 4.12's field boxes are in image
  pixels and 11.2 draws them on the frame the officer is looking at. The four
  new corners get the image's own **per-channel median**, as a tuple:
  OpenCV reads a scalar `borderValue` as `(v, 0, 0)` on a three-channel image,
  so a scalar white fill makes a white page's corners blue.
- **`MAX_DESKEW_DEG` is `m7_skew.MAX_SKEW_DEG` bound, and the guard is `>`.**
  At or past the gate's own pass threshold `m7_skew`'s search is at the edge of
  its range, so the angle is an artefact rather than a measurement; the
  argument is then returned **as it arrived** (the same object, not a copy).
  A blank page lands in the same branch. Do not add a second "too rotated"
  number here, and do not make the bound exclusive -- a document at exactly
  the threshold is one the gate passes.
- **Gate 1 is a test now, not a probe.**
  `test_the_character_readers_still_import_without_opencv` imports `document`,
  `td1`, `td2` and `td3` in a bare interpreter and fails if `cv2` or `numpy`
  reached `sys.modules`. `mrz_region.py` is the first module in the package to
  import `cv2`, so one `from .mrz_region import deskew` inside a reader would
  otherwise have broken Gate 1 with nothing in the suite noticing.
- **One `MrzDocument` for all three formats, told apart by `format`, and one
  `parse_mrz(lines)` in `document.py` that finds out which parser to call.**
  The record still lives in `td3.py` (imported by `td1.py`, `td2.py` and
  `document.py`; a test asserts all four are the same object) and carries
  `format: str = "TD3"`. **A field a format does not print is `None` and
  never an empty string** -- the seven format-specific attributes are a TD3's
  personal number and its digit, and a TD1's optional data 1 and its digit,
  its optional data 2, and a TD2's optional data and its digit. Do not
  "tidy" a `None` into `""` in a later task: `""` is a width no layout has and
  is already `mrz.parse_date`'s answer for six unreadable characters, so it
  would mean two different things.
- **The dispatcher is the only layer that can see a format, and it decides by
  shape alone.** Three lines of 30 is a TD1, two of 36 a TD2, two of 44 a
  TD3 -- all disjoint, so `MRZ_SHAPES` is a lookup and never a tiebreak --
  and a zone whose lines differ in width is **refused**, not dispatched on its
  first line. A zone of the right shape and the wrong document (a passport
  code in three 30-character lines) is handed to the TD1 parser so the
  *format's own* closed code list refuses it; do not add a content check to
  `document.py`, which would be a fourth set of rules.
- **`document.py` is above the formats and imports them; no format module
  imports it.** That is not stylistic: `mrz.py` must not import a format
  module (all three import it) and no format module can import the other two
  without a cycle through the dispatcher, so the one thing that cannot live
  in any of the four has its own module. A test asserts none of
  `td1`/`td2`/`td3` mentions `parse_mrz` or imports `document`.
- **`validate_td1_lines` (3×30) and `validate_td2_lines` (2×36) exist and the
  private `_checked_line` still does.** 3.7's trade was to move the width
  check into the zone gate; 3.14 did not, and the reason is that removing it
  from the six published line assemblers is a breaking change to an API that
  537 tests pin, and it would *open* the hazard 3.7 named -- a TD1 or TD2
  composite over a silently short span comes back **failed**, not as an
  error. What the gate buys is the missing third line. **The whole-zone
  parsers run the gate before the readers** and raise `MrzValueError`, never
  a bare `IndexError`; deleting that call passed the whole suite until the
  test was written, so keep that test.
- **The record carries no reference date and no inferred year, on purpose.**
  A caller with a date asks `mrz.infer_birth_year(document.date_of_birth,
 reference)` -- the printed field is the argument. Do not add a `reference`
  attribute to `MrzDocument` in a later task without revisiting this: it is
  the one design that could reintroduce `datetime.now()` at the edge, which
  `tasks.md` bans inside check logic, and `document.py`'s AST walk over
  `datetime`, `infer_birth_year` and `infer_expiry_year` is what keeps it out.
- **A TD1's `name`, `surname` and `given_names` are `None` and its line 3 is
  in `sources` under the layout's own `name` key.** Nothing reads line 3 yet;
  this is the gap, not a rule. A TD2's name *is* read, through `td3.py`'s
  five-step pipeline imported rather than copied, because a TD2 prints the
  same MRZ name field.
- **`YYMMDD` is parsed and range-checked in all three formats, and the rule
  is one function in `mrz.py`: `date_fault`.** Six call sites --
  `validate_date_of_birth` and `validate_date_of_expiry` in `td1.py`,
  `td2.py` and `td3.py` -- and no format keeps its own copy;
  `td2.date_fault is mrz.date_fault` is asserted. `parse_date` reads six
  characters into a frozen `MrzDate(year, month, day)` and answers `None`
  when they are not all ASCII digits. **Do not copy the month range into a
  format module, and do not make `parse_date` answer the range question** --
  the split is what keeps "this date cannot exist" apart from "this field
  could not be read", which is 2.14's distinction one level up.
- **`"993199"` and `"013200"` are refused by name -- the month -- and
  `"AAAAAA"`, `"<<<<<<"`, `"abcdef"` and `"74o812"` still parse in all three
  formats.** That last half is deliberate and load-bearing: a character the
  standard does not print in a date field is a *misread*, and the check digit
  printed beside it is what reports a misread. Refusing it in the reader would
  throw that finding away and report an OCR slip as a document nobody could
  read. Do not "fix" a later task by widening the refusal to characters.
- **`MrzDate.year` is two printed digits (`0`-`99`) and carries no century,
  and `date_fault` judges no century.** `"000101"`, `"000229"` and `"020229"`
  are accepted, and there is no fourth field a century could hide in. **3.12 and
  3.13 have now answered it for both dates and the record still holds no
  century**, because the answer is a function of a reference date and comes
  back as a plain `int` *beside* the record. Do not add a `century` field to
  `MrzDate` and do not have any reader fill one in: the two dates are answered
  under different rules, and one record has to hold both.
- **`infer_birth_year` and `infer_expiry_year` are the only places a century is
  invented, and each is named for the date it answers for rather than
  `infer_century`.** **They are two functions and must stay two**: a single
  function with a `kind=` argument would satisfy every test in `test_mrz.py`
  except the five-row disagreement table, which exists for that reason.
  `infer_birth_year`'s rule: the most recent year carrying the two printed
  digits that has
  already happened, was a day that year had, and is no more than
  `MAX_BIRTH_AGE` (120) years before the reference. Only two centuries are
  candidates. **Three things a later task must not quietly change:**
  the "not yet" test is on the whole *date*, not the year (`"260930"` read on
  the 30th is 2026, `"261001"` read on the 30th is 1926); the previous century
  is reached *two* ways, and the "too old" one is a bound on how far back the
  rule may reach rather than the only way into it; and the answer is a plain
  `int`, not a `datetime.date` and not an `MrzDate`.
- **`infer_expiry_year(text, reference)` is the same shape read the other
  way: the nearest year carrying the two printed digits that has *not* passed
  and was a day that year had.** Only two centuries are candidates
  (`century + YY`, `century + 100 + YY`, most recent first) and **there is no
  band** -- `MAX_BIRTH_AGE` is named for the date it bounds and its reasoning
  (nobody is 121) is about a person, whereas two digits repeating every
  hundred years *is* the bound on an expiry. **Do not add an expiry age
  constant**: the 700-case sweep asserts `unplaceable == 0` and
  `0 <= found - reference.year <= 99`, and an AST walk asserts
  `MAX_BIRTH_AGE` is absent from this function's `ast.Name` nodes while present
  in the birth rule's.
- **The two rules differ in one place that is not a mirror image: the day
  itself is admitted by both.** A document is valid *through* the day it
  expires, so `"260930"` is 2026 for both rules -- a birth today has already
  happened and an expiry today has not passed -- and `"260929"` is a birth of
  today and an expiry a century on. The expiry rule can also **run out of real
  days** where a birth rule cannot: `"000229"` is 2000 for a birth in 2026 and
  `None` for an expiry, because 2100 was not a leap year, and it stays
  unplaceable until 2400.
- **`reference` is a required argument and no caller may leave it to the
  clock.** `datetime.now()` inside check logic is banned by `tasks.md`, and
  3.12's answer changes with the date it is read on -- the same six characters
  are 1906 on 2005-12-31 and 2006 on 2006-01-01 -- so a default would make a
  screening's finding depend on when it ran. The ban is pinned on the
  signature and by an AST walk of the module, not a substring, because the
  docstrings name `datetime.now()` to say it is unused.
- **`None` from either rule means "this document does not tell us", and it is
  reached three ways: unreadable characters, a `date_fault`, or no century that
  makes the six characters a real day on the right side of the reference.** The
  caller cannot tell them apart and does not need to -- an officer must never
  be handed a year this project invented, because there is no way to mark it as
  invented later. **The first two are shared and asserted row for row across
  both functions**; the third differs, and the expiry's is the one that can be
  reached with a perfectly good leap-century date. **Ask `parse_date` before
  `date_fault`**: `date_fault` answers `None` both for "unreadable" and for "no
  fault", so a six-letter field read through it alone is a date of zero.
- **`MONTH_DAYS` holds twelve maxima and February's is 29, not 28.** A date
  carries two digits of year, so whether a particular February had a 29th is
  not answerable from what the line printed; 29 is the largest that refuses
  nothing genuine. Flattening every month to 31 accepts more nonsense and
  refuses nothing; answering leap years here needs a century this package has
  not been given. The tuple is pinned against a longhand copy in
  `test_mrz.py` and every month is measured against every day from 00 to 32
  (462 cases).
- **`date_fault` does not judge width, and `parse_date` does.** How wide a
  date is belongs to the layout table all three validators read it from;
  2.11's monkeypatch test moves a date field to five characters and fails if a
  width rule leaks in from `mrz`. A caller holding five characters hears about
  it from `parse_date`, and the formats pass it over because they have already
  judged it against their own table.
- **A date is still returned exactly as printed, in every format, and no
  reader tidies one.** The check digits beside both dates are computed over
  the characters as printed. This task added a refusal, not a cleaning step.
- **A TD2 is a TD3's shape at 36 characters a line, and the whole of the
  8-character difference is the optional data.** `TD2_LINE_1` is the
  document header and the name (1-2, 3-5, 6-36) and **carries no check digit
  at all**, so its last position is the last filler of the name.
  `TD2_LINE_2` shares a TD3's line 2 field for field and position for
  position up to 28, then spends 6 on `optional_data` (29-34) where a TD3
  spends 14 on a personal number, and has a check digit over the optional data
  at 35 before the composite at 36. **Five check digits are printed and all
  five are on line 2.** Do not widen `optional_data` to 14 in a later task,
  and there is no name field on line 2 -- both the task lists that said
  otherwise have been corrected.
- **`tasks.md` 3.9 and 3.10 both described a TD1, and both are now corrected
  against the table 3.8 pinned.** 3.9's line 1 list was `TD1_LINE_1` verbatim
  and 3.10's line 2 list was a TD1's field list; each task parsed the
  standard's line instead of its own task text and rewrote that text. 3.10's
  composite span was the same failure one level deeper -- `TD1_COMPOSITE_
  SPANS`'s three line 2 spans copied verbatim -- and 3.10 settled its own
  instead, the way 3.7 did. **Nothing in `tasks.md`'s Part 3 has been taken on
  trust where a table pinned by 3.8 existed to check it.**
- **The TD2 composite's span is 62 characters -- line 1's whole name at 6-36,
  then line 2's 1-10, 14-20 and 22-35 -- and it is the TD3's composite with
  the name in front and the last eight positions dropped.** Do not "fix" it to
  `tasks.md`'s original text; a test measures why that text cannot be this
  format's. The three arguments, in order of weight: it covers every printed
  digit (10, 20, 28, 35), it skips the nationality at 11-13 and the sex
  marker at 21 as both siblings' spans do, and every span is a run of whole
  fields -- the TD1 is the only format in this package with a span that cuts
  a field, and that cut is the standard's own. **This repository holds no copy
  of Doc 9303, so the span is the standard's as this project states it**; it is
  the highest-exposure claim in the package and the first thing a sourced copy
  should be checked against.
- **The name is inside the composite, so 3.9's unfilled padding is load-bearing
  in fact.** `validate_name` returns the field with its eleven fillers and
  nothing tidies it; a filler changed in the name's padding moves the
  composite row and no other. (A filler printed as "A" is worth zero, exactly
  as the filler is, so that particular edit is invisible to every digit here --
  2.14's blind spot, not a defect in the span.)
- **A TD2 line 1 is three fields, and the third one is a person.** 3.9 added
  `td2_field`, a closed `TD2_DOCUMENT_CODES` (`{"V<", "V"}`), three
  `parse_`/`validate_` pairs and `parse_td2_line_1`, which returns a read-only
  `MappingProxyType` keyed by the layout's own field names in printed order --
  the shape 3.14 inherits, and **no record type yet**. 3.10 added line 2's six
  `parse_`/`validate_` pairs and `parse_td2_line_2`, its twin in every respect,
  with eleven fields in printed order.
  `validate_name` judges the field's **width and nothing else** and the
  padding comes back with it, for 3.10's arithmetic as much as for the
  caller. Do not add a rule about the characters: the names a visa carries are
  not a set anyone can enumerate, and a diacritic or a lower-case read is a
  misread a flag wants, not a reason to drop the document.
- **`td2_check_digit_results` reports five rows, and this format's correct
  specimen gives five `True` and no `None`** -- the one thing it does not share
  with the TD1's, because this optional data is filled in and its own digit
  position prints a digit. The unused case is the interesting one: six fillers
  with the filler in the digit position give `found 0, expected None, passed
  None`, and with that row unable to say "failed", **the composite is the only
  row that can see an edit to the field.** Do not "fix" that row in a later
  task by making it `False`.
- **On a TD2 the document code and the issuing state are what tell the two
  lines apart, and neither is a check digit.** A line 2 whose number starts
  `V<` is a good visa code, so the state at 3-5 is the second half of the
  answer. **3.10 confirmed the other direction and it is worth knowing: a line
  1 handed to `parse_td2_line_2` is not caught at all** -- its 1-9 read as a
  short padded number, its 11-13 as "SON" (an MRZ prints names in capitals) and
  its 21 as an "M" -- so 3.14's dispatcher is the thing that must guarantee
  the right line. What *does* happen is that all five rows come back
  "unreadable" rather than "failed", which is 2.14's rule one level up.
- **The TD1 composite digit lives on line 2, position 30, and this is the one
  thing about the format that is easy to get backwards.** Line 1's position 30
  is the check digit over optional data 1 (16-29). The composite is *printed*
  at the end of line 2 and *computed* over characters on both of the first two
  lines. Every span in `TD1` stays inside one line, and 3.7 is the first
  task in this format that must read two lines to answer a question about one
  digit. **Which line 1 characters are inside it is settled: line 1 1-10 and
  15-30, plus line 2 1-7, 9-15 and 19-29** -- `TD1_COMPOSITE_SPANS`, 51
  characters. `tasks.md` 3.7 was right and `td1.py` was wrong; 3.5's flag on
  the claim is what stopped the wrong one being inherited quietly.
- **The composite's span is positions on a *named line*, and that is forced
  rather than stylistic.** Line 1 1-10 stops five characters into the
  nine-character document number, so no list of whole field names can name it
  -- this is the one place `td1.py` cannot use `td3.py`'s field-name spans.
  **The consequence to remember is that document number positions 11-14 are
  outside the composite:** editing the tail of a number fails the number's own
  row and nothing else. Every other span is a run of whole fields, and a test
  asserts that the one cut is the document number and nothing else.
- **`td1_check_digit_results` reports five rows, and a correct specimen gives
  four `True` and one `None`.** The `None` is `optional_data_1`: an unused
  optional data field prints filler in its check digit's place, so there is
  no printed half to disagree with. Do not "fix" that row in a later task by
  making it `False` or by having the parse reject the line -- 2.14's rule is
  why it is a third answer, and the composite is the only row that can catch
  an edit to that field.
- **`parse_td1_line_1` is the shape 3.6 and 3.14 inherit, and it is a
  read-only mapping rather than a record, and 3.6's `parse_td1_line_2` is
  its twin rather than a different shape.** Each line gets its own mapping;
  3.14 decides what wraps them. Do not add a TD1 dataclass before that task.
- **`TD1_SEX_MARKERS` holds four characters, and the reasoning is in the
  module docstring because the set is a decision rather than a lookup.**
  `{"M", "F", "X", FILLER}`. If a sourced copy of Doc 9303 later shows the
  TD1 sex field reading `M`, `F` or `<` alone, drop `"X"` and nothing else
  moves. Do not widen it to a rule, and do not add `TD3_SEX_MARKERS` as a
  dependency -- the two sets are separate so the formats can differ.
- **A date of birth or expiry in a TD1 is judged for its width and its range,
  and the range check is `mrz.date_fault`'s rather than this format's.**
  `"993199"` and `"013200"` are refused by name; `"AAAAAA"` and `"<<<<<<"`
  are not, and that half is deliberate -- a character the standard does not
  print in a date field is a misread for the check digit beside it to report.
  The same split is in `td2.py` and `td3.py`, and the three formats cannot
  disagree about it.
- **A TD1 field is returned with its filler, and no field is tidied.** The
  two check digits are computed over the printed characters, so stripping a
  field's padding would change the digit 3.7 computes. The exception to "no
  cleaning" is nowhere in this format yet.
- **`TD1_DOCUMENT_CODES` is `{"I<", "I"}`, and a bare `I` is accepted for
  `td3.py`'s reason** -- position 2 is filler, so a code that lost it is the
  same document, and the filler's value of `0` means dropping it cannot change
  a digit. `P<` and `V<` are refused: well-formed codes belonging to other
  formats. Recognising more codes is a sourced-list question, not a reader's.
- **A layout field is a span of positions, not a rule about characters.** The
  document number's check digit (line 1, position 15) is optional in the
  standard and may print as `<`; the table cannot record that, and whether a
  printed `<` means "no digit" or "a misread digit" is a reader's question --
  and the span does not care, because the optional digit is inside the
  composite's arithmetic either way.
- **3.3's decisions are unchanged by this task.** `CheckDigitResult` and
  `mrz.check_digit_results` are already format-agnostic and take their
  pairings from the caller, so TD1's five printed digits will hand them their
  own list the way `TD3_CHECK_DIGIT_FIELDS` does.
- **`MrzDocument` holds evidence and verdict as two separate things, on
  purpose.** `composite_check_digit` and its four siblings are the characters
  the line printed; `check_digit_results` is this parse's reading of whether
  they agree. Collapsing them would let a parse "repair" a digit to make its
  own verdict pass, which is what 2.14's test exists to fail.
- **`passed` is `bool | None`, and the `None` is load-bearing.** A caller
  asking "did this document pass" has to handle the third answer. Do not add
  a `failed_fields` convenience or a bool shortcut in a later task without
  deciding what it does with an unchecked row -- "everything that is not
  `False` passed" is the bug this design exists to prevent.
- **`td3.py` may delegate but may not reimplement.** The rewritten 2.2 guard
  is the enforcement, and the positive assertion
  `td3.check_digit_results is mrz.check_digit_results` is the part that keeps
  a second copy of the arithmetic from being written here.
- **`td3_composite_input` is still the only assembler of the 39 characters**,
  and `td3_check_digit_results` still judges nothing by itself. 3.1's
  decisions are unchanged by this task.
- **The five printed digits are read into the record twice on purpose** --
  once as the characters the line printed, once as the `int` a verdict
  compares -- and the two are not allowed to be the same field.

### Known Issues / Blockers

- **`group_lines` makes the greyscale exposure visible rather than worse, and
  4.6 was measured not to close it -- 4.7's count is what does.** The six
  specks 4.4 cannot refuse now come back as **two lines of 2 and 4 blobs**,
  sitting on the same two baselines the print uses (rows 108-118 and 178-188),
  so a caller sees two lines of between two and four blobs each rather than an
  empty result. 4.6's two scores pass both of them, and that is arithmetic
  rather than a gap: they are all ten rows tall like each other and a leading
  apart like each other, and a consistency score cannot tell a line of two
  blobs from a line of forty. (4.5's own note claimed 4.6 would throw them
  away; that sentence is corrected in `group_lines`' docstring, and this
  bullet is the standing version of it.) **4.7 is therefore the step that has
  to catch this**, with an exact shape rather than a band -- and if 4.7 cannot,
  the honest place for the fix is still 4.2's cut, because the caller handed
  `group_lines` a frame that skipped `binarize_inverted`, and not a fifth
  threshold anywhere in Part 4.

- **`filter_glyphs` only partly cures a greyscale frame, and a partial answer
  is the worse of the two failures.** 4.3 recorded that `extract_components`
  accepts a greyscale frame and answers with the page; the band now removes
  that page and most of the rest, so the failure changed shape rather than
  disappearing. Measured: 24 components in, **6** survive, each one a band of
  *paper* 10 rows tall and 5 or 6 pixels wide - inside both bands, and shorter
  than the shortest glyph the fixture drew, so no band on height and aspect
  separates it. **Do not add a third threshold to hide this**: the caller that
  hands a greyscale frame in has skipped `binarize_inverted`, and 4.2's cut is
  the fix. A test asserts the exact 6 so the exposure stays a number.

- **A photograph with texture leaves glyph-sized fragments the band cannot
  refuse, and that is `ADAPTIVE_C`'s exposure rather than 4.4's.** A
  flat-toned photo box comes through as one blob and is refused whole (see
  above), but the same box filled with coarse texture gives ~12 fragments of
  5-13 pixels that sit inside both bands, on a page where the flat box gives
  one. A height band cannot tell texture from a character and should not be
  asked to. If this shape shows up in 27.1's corpus the answer belongs in
  `ADAPTIVE_C` and `ADAPTIVE_BLOCK_SIZE`, retuned on measured captures - **not**
  in `GLYPH_MIN_HEIGHT_PX`.

- **The four band constants are sized on a fixture 4.14 deletes, and three of
  the four rules are only checkable because the fixture still exists.** The
  floor (at least half the tallest glyph), the ceiling (under half the line
  pitch), the aspect floor (a fifth) and the aspect ceiling (under three) are
  the durable part and `test_the_band_is_held_to_the_rules_it_is_pinned_on`
  checks all four against the frame. **4.14 must re-run that test against the
  real generator**, and if the glyph size or the line pitch moves, re-derive the
  four numbers from the rules. What 4.4 has bought is not four tuned values but
  four numbers with a stated reason each.

- **The two halves of the band are only as independent as the fixtures make
  them, and one fixture cannot be both a photo and a signature.** The photo
  case proves the height ceiling and the signature case proves the aspect
  ceiling because each was drawn to sit inside the *other* band. A real capture
  can produce a blob that both bounds refuse and no test here would say which
  one did, and 4.5 will group whatever survives regardless. That is acceptable
  for a filter, but it means neither constant can be retuned in isolation
  without re-running both cases.

- **`extract_components` accepts a greyscale frame and answers with
  the page, and the only thing stopping that is the caller remembering to
  binarise.** OpenCV reads every non-zero pixel as ink, so `to_gray`'s own
  output handed straight in -- skipping `binarize_inverted` -- gives 24
  components on this repository's fixture and one of them 600 pixels wide,
  which is 4.2's page-turned-white failure reached by a different route. **A
  three-channel frame is a `cv2.error` and a float32 frame is a `cv2.error`,
  but a greyscale one is accepted silently, and the two frames look equally
  like "an image" at the call site.** Refusing it would need a `raise`, which
  1.9's rule does not allow this module to have, and the guarantee belongs
  where the frame is produced rather than where it is consumed:
  `binarize_inverted` is the only function that can turn a frame into a frame
  this one can read. Do not add a shape check here. **4.4 inherits the
  exposure in a worse form, because a height band on a page-sized blob is how
  a mis-binarised frame would be *nearly* rejected** -- so 4.4's negative
  tests should include a greyscale frame.

- **OpenCV's `connectedComponentsWithStats` takes `labels` as its second
  positional parameter, so `connectivity` passed positionally is silently
  discarded and the default is used instead.** The documented signature reads
  `(image[, labels[, stats[, centroids[, connectivity[, ltype]]]]])`, and the
  default is 8, which is exactly why this cannot be found by comparing
  answers: measured, the positional form returns the same single component on
  a twelve-pixel diagonal stroke for both `4` and `8`, where `connectivity=4`
  returns twelve. **`mrz_region.extract_components` names the argument and a
  test records the call to keep it that way, but 4.2's test helper
  `_widest_and_tallest` still passes `8` positionally.** Its answers are
  correct and 4.2's tests are green, so this is not a bug -- but the argument
  there does not mean what it looks like it means. If anyone sweeps that
  helper, change the call and nothing else; do not treat it as the fix for a
  failure, because there is no failure.

- **`CONNECTIVITY = 8` is a decision about glyphs, and 8 is also the value
  that hides its own cost.** It rests on a measurement -- a diagonal MRZ
  stroke is twelve components under 4 and one under 8 -- and the cost is the
  opposite mistake, two neighbouring glyphs whose corners touch reading as a
  single blob. That cost is already in the fixture: 51 components from 53
  printed characters, so two pairs have merged at the cut. **4.10 has to
  segment those merged blobs whether or not they were ever separate glyphs,
  and 4.5 has to group blobs that may be two characters.** Do not change the
  constant to 4 to "fix" a merge; that trades two merged glyphs for every
  `7`, `4` and `2` in the document being cut in half, which 4.4's band would
  then reject outright. A per-caller connectivity argument was considered and
  refused for `ADAPTIVE_C`'s reason -- one definition of "connected", or 4.4
  filtering on a different one than 4.5 grouped with.

- **`MrzComponent` is a record with no methods, and that is enforced from two
  sides rather than one.** `bbox` and `centroid` are derived properties, so a
  caller cannot be handed a box that disagrees with the parts it was derived
  from; a test asserts the seven fields and the two public attributes
  exactly, because a method added here is where a second judgement about
  what a glyph is would grow -- 4.4's height band, written twice. **`area` is
  carried but nothing filters on it.** It is one of the five numbers the cut
  already produced and 4.4 may want it, but the standing note stands: if 4.4
  finds itself needing an *area* filter as well, that is `ADAPTIVE_C` and
  `ADAPTIVE_BLOCK_SIZE` having been asked to do 4.4's job, and the fix belongs
  in them once 27.1's corpus can measure it.

- **`MrzComponent` is in `__all__` and is a class, which retired a written
  assertion; the rule it stood for did not change.** The source-side test
  asserted `"class " not in source`, which is a proxy for a rule about *error
  types*, and 4.3 introduced this module's first record. It is now an
  `ast.Raise` walk plus a `ClassDef`-bases walk plus
  `not issubclass(MrzComponent, BaseException)` -- strictly more than the two
  substrings, which were also a landmine: `"raise "` appears in this module's
  own docstrings while they explain the rule. **If a later task adds a
  genuine second error type to this module, that test is the thing that
  should fail**, and it will.

**`ADAPTIVE_C` is this project's own number, and this is the largest unsourced
claim in `mrz_region.py`.** 4.1's `MAX_DESKEW_DEG` was bound to `m7_skew`'s
own constant, and 4.2's `ADAPTIVE_C` has no such anchor: nothing in this
repository can say how much darker than the paper a genuine MRZ stroke is.
There is no copy of Doc 9303 here, no printed specimen, and the fixture is
**drawn** -- `upright_mrz` paints 0 on 255, so its strokes are 255 levels below
the paper by construction and say nothing about real print. **This is a
starting point, not a tuned value, and the direction of the risk is the useful
part**: raise it and faint print disappears (a thermally printed MRZ is the
case to worry about), lower it and speckle returns on grainy captures. 4.3 and
4.4 are the first tasks that can see the consequence, and the honest way to
retune it is to measure on a real capture in 27.1's corpus and re-run the
grain test -- not to argue from the fixture. Do not add a per-format variant or
a second threshold on the strength of one frame.

**The block size's rules are checked against a fixture that 4.14 replaces, and
the sweep that justifies the constant is a property of that fixture.** Every
odd block from 11 to 61 reading identically is a fact about 15-pixel glyphs on
a 70-pixel pitch, not about documents. 4.14 must re-run
`test_the_reading_does_not_depend_on_which_odd_block_is_used` against the real
generator and, if the glyphs or the pitch move, revisit `ADAPTIVE_BLOCK_SIZE`
against the three rules rather than to the number that used to work. The rules
are the durable part; the constant is not.

**A grainy capture leaves speckle in the frame on purpose, so 4.4 has to be
written expecting it.** The row-band test deliberately has **no threshold** in
it, and `grainy_mrz` is the frame it cannot answer for: at sigma-6 grain the
page has rows of isolated single pixels and 74 bands where the other three
frames give 2. The claim made instead is the one 4.4 depends on -- the widest
and tallest components are `(22, 15)` on the grainy page and the clean one
alike, so a height band rejects the speckle and keeps the print. **If 4.4
finds itself needing a connected-component *area* filter as well, that is
these two constants being asked to do 4.4's job**, and the fix belongs in them
only after the corpus in 27.1 can measure it.

**`deskew` is the one place in the MRZ package where a `cv2.error` can
escape, and that is a decision rather than an oversight.** 1.9's rule is that
a caller writes `except mrz.MrzValueError` once and has seen every failure the
package can report. That is true of `mrz`, `td1`, `td2`, `td3` and
`document`, and it is **not** true of `mrz_region.py`: a one-channel frame (or
`None`, or anything that is not an image) reaches `m7_skew._scan_skew`'s
`cvtColor` and comes back as `cv2.error`, which is not an `MrzValueError`. A
greyscale test was written and then deleted rather than satisfied, because the
alternative -- converting quietly inside `deskew` -- would run the estimator on
a frame its author never saw. **A caller that wants the one-error-type
property back must hand `deskew` a three-channel BGR image, and 4.2's
`to_gray` is downstream of this call rather than upstream of it.** Do not add
a `try`/`except` around it in a later task: a caught `cv2.error` that returns
the image unchanged is a silent failure with exactly the same shape as a
legitimate no-op.

**The corner fill is the median of the whole frame, which is the paper for a
document photograph or scan and the wrong answer for a tight crop of the MRZ
itself.** `_border_fill` measures what dominates the image; an image that is
*mostly* ink fills its new corners with ink, and 4.3 would then see one
component spanning the page. This is a known limit rather than a bug -- the
working image this helper exists for is a document frame, and a caller holding
a cropped zone is holding something the whole of Part 4 is about to find. If
4.13's empty-result path ever has to deskew a tight crop, fill from the border
pixels rather than the median and say so in the docstring.

**`skew_deg` has two answers where the rest of the package has one.** It
returns a `float` from the scan estimator and a `float | None` from the photo
estimator, because that is what `m7_skew` returns -- `None` meaning the
text-block estimator found no text at all. `deskew` collapses both into the
same behaviour, which is why no caller has to handle them separately, but a
caller that wants to *report* the reason cannot read it out of the return
value. 4.13 is the task that reports reasons, and it should take the reason
from `m7_skew` directly if it needs one.

**`MONTH_DAYS` is a decision about the calendar rather than a quotation from
Doc 9303, and February's entry is the one to know about.** The other eleven
entries are ordinary civil-calendar knowledge, but the standard does not print
a day count anywhere, so nothing in this repository could confirm them and
nothing needs to: they refuse nothing genuine in any century. **February is 29
rather than 28 because a two-digit year cannot say whether a particular
February had a 29th, and the century that could say it is 3.12's.** The
failure modes are not symmetric, and the tuple goes against the cheaper error:
29 accepts a date that no century can make real ("000229" is only real in
leap centuries), while 28 would refuse a real one -- a 29 February of a birth
date or an expiry. **3.12 and 3.13 have now built the thing that could say it,
and the entry does not change**: `date_fault` still judges range with no
century in hand, and the two inference functions are where a 29th of February
is resolved against the year it was really in. Do not "correct" it to 28, do
not move leap-year logic into `date_fault`, and do not have a format validator
call `infer_birth_year` or `infer_expiry_year` to settle a 29 February -- a
range check that needed a century would have had to invent one, and 3.11's
whole point was that it does not.

**The date rule is the one place in this package where the shape of the
standard and the shape of the calendar are two different sources, and only one
of them is this project's to quote.** `YYMMDD` and the six-character width are
the standard's, stated from the same source as the layout tables and carrying
the same standing caveat -- this repository still holds no copy of Doc 9303.
The month and day ranges are not. That is not a gap: it is why the rule can be
right without the document.

**`td2.py`'s positions are stated from a standard this repository does not
hold, and that is the same class of claim as the two already listed below --
except that this one is the third thing in this package a table cannot check
for itself.** The file list in `test_td2.py` is a second copy of the table
written longhand, so a boundary one character out fails, and six mutants were
run to prove it; but a copy can only catch a *drift*, not a wrong first
draft, and a wrong first draft is exactly what 3.5 wrote down and 3.7 had to
take back. **The structural claims 3.8 does make are therefore stated as
claims:** a TD2 line 2 is a TD3 line 2 to position 28 and then 8 characters
of optional data, a TD2 prints five digits and all five are on line 2, and
line 1 prints none. A sourced copy of Part 7 is the only thing that turns
those into a lookup. Not a blocker -- nothing downstream exists yet -- but it
is listed here rather than buried, and **3.9 has now acted on it**: 3.9 quotes
a printed visa, and the exposure turned out to be smaller than 1.6's rule
assumed, because a TD2 line 1 prints no check digit. **The unverifiable part
of the specimen is its name, not a digit**, no arithmetic here computes over
a name, and the one thing that could be checked about the quoted line -- every
character on it is one `mrz.CHAR_VALUES` prints -- is. **3.10 paid the sharper
edge and it is now the largest unsourced claim in the package:**
`TD2_COMPOSITE_SPANS` (line 1's name at 6-36, then line 2's 1-10, 14-20 and
22-35) was settled by argument and not by a source. The three arguments are
that it covers every printed digit, skips the nationality and the sex marker as
both siblings' spans do, and is a run of whole fields throughout -- but no
test here can confirm any of them against a source, only against the format's
own shape. **A wrong span makes every genuine visa's composite row fail**, so
this is the first claim a sourced copy of Part 7 should be checked against,
and the argument in the module docstring is written to be checkable when one
exists.

**The TD2 specimen's two derived digits are this project's arithmetic, and
that is stated rather than hidden.** `test_td2.py` quotes
`L898902C<3UTO7408122F1204159ZE184283`, of which the "3" at 10, the "2" at 20
and the "9" at 28 are confirmed against the characters beside them (they are
the same three the TD1 and TD3 specimens print for the same fields), while
**the optional data's digit ("8") and the composite ("3") are computed by
`mrz` and written in.** 3.7 found a remembered TD1 composite digit wrong by
exactly that test, so the fixture carries the arithmetic's answer. **A green
composite row means these 62 characters, this printed digit and this verdict
are one story, and never that any real visa carries it** -- exactly as 1.6
recorded for a TD3's composite. The characters themselves are the standard's
own (the same fictitious visa, with the standard's document number "L898902C<"
and the first six characters of its personal number), and every one of them is
one `mrz.CHAR_VALUES` prints.

**The specimen's name is a remembered value, and it is stated rather than
hidden.** `test_td2.py` quotes the sample visa's line 1
(`V<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<`) while this repository holds no copy
of Doc 9303, so the characters are the standard's as this project states them
and not a list anything here could look up. **A green parse over it means the
36 characters, the three widths and the field order are one story -- never
that this is a real visa**, exactly as 1.6 recorded for a TD3's composite.
**3.10 made it load-bearing for the first time**, by putting the whole name
inside the composite's span: a wrong name would now change a verdict. The
readers still judge width and alphabet only, so a name is never refused; it is
the composite row that would move.

**The TD1 composite's span is now settled, but it was settled by argument and
not by a source, and that is the standing caveat to carry forward.**
`TD1_COMPOSITE_SPANS` is `tasks.md` 3.7's span -- line 1 1-10 and 15-30, line
2 1-7, 9-15 and 19-29 -- and `td1.py`'s earlier "6-14 and 16-29" was wrong.
The three reasons are in the module docstring and none of them is a quotation:
the span starts at line 1 position 1, it includes every check digit line 1
prints, and it reads line 2 in the shape a TD3 and a TD2 read theirs.
**This repository holds no copy of Doc 9303**, so the span is stated as the
standard states it rather than as a list something here could look up, and a
sourced copy of Part 4 is the only thing that would upgrade that to a lookup.
It is not a blocker -- the span is pinned by longhand expectations, by six
mutants that each fail 9 to 13 tests, and by a structural test that catches
any position the layout would disagree with -- but it is listed here beside
`TD1_SEX_MARKERS` because it is the second claim in this module of exactly
that kind.

**The specimen's composite is a derived value, and 3.6's remembered `6` was
wrong.** `SPECIMEN_LINE_2` position 30 is now `7`, which is
`mrz.check_digit` over the standard's 51 characters. This is the same choice
`test_td3.py` made and for the same reason, so **a green composite row means
"these 51 characters, this printed digit and this verdict are one story" and
never "this card is genuine"** -- the other four printed digits on the
specimen are quoted and confirmed against their own arithmetic, so a
misremembered line is very unlikely to have survived, but the composite has no
source behind it at all. If a sourced copy of Part 4 later publishes the
specimen's line 2, that one character is the thing to check first.

**`TD1_SEX_MARKERS` is stated from a standard this repository does not
hold, and that is a second unverified claim of the same kind.** Not a
blocker -- the set is four characters, its reasoning is written down, and
one of the two ways it can be wrong is the one that refuses a genuine card.
It is listed here so nobody reads the docstring's ICAO citation as a lookup
that happened. `TD3_SEX_MARKERS` carries the same note from 2.12.

Otherwise: none. The suite is green and `check-all.ps1` exits 0.

Three things 3.5 inherits from 3.3, none of them a blocker:

- **What a composite failure is worth is still not characterised.** 3.3 makes
  the *shape* of the answer visible, not the strength of the claim. A forger
  who edits a covered field *and* recomputes that field's own digit defeats the
  per-field rows; the composite catches most such edits but not all. A caller
  reading the list sees the field and the composite fail together, which is
  the honest reading -- the composite cannot say which came first. Nothing
  here writes a detection claim down.
- **2.14's blind spot is now a property of the record, not only of the
  arithmetic.** A substitution inside one ICAO value class passes all five
  rows. The test enumerates all 25 of them for the specimen's document number
  so the count is measured rather than remembered, and a later change to
  `char_value` or to the weights would have to move it deliberately.
- **`td3_check_digit_results` raises `KeyError`, not `MrzValueError`, if
  `sources` lacks a field a pairing names.** Deliberate: `sources` is this
  package's own map built from `TD3_LINE_2`, every pairing names a field of
  that layout, and a missing key is a caller bug rather than a wrong document
  -- dressing it up as one would put a `MrzValueError` in a log describing
  nothing about any passport. It is the only non-`MrzValueError` exit in the
  MRZ package, and 1.9's invariant is about what the package raises for MRZ
  input.

### Immediate Next Step

**4.6 is done, so the next task is 4.7.** Infer the document format from line
count and median glyph count per line (2x44, 3x30, 2x36), with a test per
format. 4.6 hands it a tuple of tuples of records and seven decisions, none of
which 4.7 should reopen:

- **`filter_lines` returns a tuple of tuples -- lines down the page, glyphs
  across it -- and there is still no `MrzLine` record.** A group *is* a tuple
  of components; anything a record would carry (top, bottom, left, right) is
  `min`/`max` over members that already exist, and 4.7's two numbers are
  `len(line)` and the median of it. A record here would be one more place for
  a judgement to live, and `MrzComponent` is still data and nothing else.

- **4.7's line count is what catches a line of two blobs, which is the
  exposure 4.5 handed over and 4.6 measured as not its own.** The greyscale
  specks arrive as two lines of 2 and 4 blobs and both scores pass them, so
  the count has to be an exact shape rather than a band: 2 and 4 are neither 44
  nor 36, and a band wide enough to admit a four-blob line would admit a line
  that had lost half its characters.

- **This fixture prints 25 and 28 characters, which is no format's length, so
  4.7 cannot be tested against it.** `LINES` is a 25- and a 28-character pair;
  the three real shapes are `td3.TD3_LINE_COUNT`/`TD3_LINE_LENGTH` (2x44),
  `td1` (3x30) and `td2` (2x36), and Part 3 already holds them, so the answer
  has to come from those constants rather than from a list written again here.
  **Blobs are not characters either**: this cut merges two pairs per line, so
  the fixture's 24 and 27 blobs are its 25 and 28 characters, and a real
  44-character line comes back nearer 40. Write the three format cases
  longhand, as tuples of tuples of `component_record`s, the way 4.6's stray
  line was written -- and the fixture's own two lines are the negative case
  for free, because a median near 26 is no format.

- **The median is over the lines that survived, so a set carrying one real
  line and one stray line has a median that is no format's length.** 4.7's
  answer there is "no MRZ here", not the nearest shape: 4.13 needs to be able
  to say that, and a detector that always picks the closest format cannot.

- **Nothing here re-opens 4.4's band or 4.6's two.** A blob that survived 4.4
  is glyph-plausible by definition and a group that survived 4.6 is on the
  leading; 4.7's only question is what shape the set has. 4.6's stray-line
  test is the standing proof that a third line of type is refused before 4.7
  ever counts it.

- **`MrzComponent.area` still goes unread.** Nothing in Part 4 filters on it,
  and neither 4.5's grouping nor 4.6's scores wanted one. If 4.7 finds itself
  wanting an area threshold, that is this note firing again: the answer belongs
  in `ADAPTIVE_C` and `ADAPTIVE_BLOCK_SIZE`, once 27.1's corpus can measure
  it.
