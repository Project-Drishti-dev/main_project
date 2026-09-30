"""Where on the document the MRZ is: Part 4, finding *where* rather than *what*.

Parts 1-3 turned a zone of characters into a :class:`~app.pipeline.tier0.td3.
MrzDocument`.  Nothing in them knows an image exists, and that is deliberate:
``mrz``, ``td1``, ``td2``, ``td3`` and ``document`` load neither ``cv2`` nor
``numpy``, so a caller can read a zone from a database row with no OpenCV in
the process.  This module is the first file in the package to touch pixels,
and its job is to keep that property true rather than to enjoy breaking it --
so it imports nothing from its siblings except through the package boundary,
and it defines no error type, because :data:`app.pipeline.tier0.mrz.
MrzValueError` is the only one this package is allowed to raise.

**The skew angle is not measured here.**  ``app.quality_checker.m7_skew``
already answers "how far round is this image" from the text rows, and a second
estimator written in this file would be a second answer to the same question:
they would agree on flat scans and disagree on exactly the photographs -- a
held document, a page photographed off-axis -- where the answer decides
whether the MRZ is found at all.  So :func:`deskew` calls
:func:`m7_skew.text_skew` and rotates by whatever it is told.  4.1 is the only
step in Part 4 that reuses code this project already ships, and it is written
so that the reuse is checkable: a test pins this module's reading to
``m7_skew``'s, and a second one replaces ``m7_skew``'s reading with a sentinel
and asserts the rotation follows it, so a reimplementation cannot pass
quietly.

**The frame does not move, and the corners are filled with the image's own
median colour.**  Rotating into a larger canvas would lose nothing, but every
polygon 4.8 emits and every field box 4.12 returns would then be offset from
the frame the officer is looking at, and nothing downstream would carry the
offset.  Keeping the size means the answer to "which pixels" is unchanged by
this step, and the only cost is the four corners -- which is why they are
filled from what is already in the image rather than from an assumed white:
a median is measured, and a scan of a white page and a photograph of a dark
one both get corners that look like their own page.

**A rotation this helper will not apply is one the quality gate has already
rejected.**  :data:`MAX_DESKEW_DEG` is ``m7_skew``'s own pass threshold and not
a second number: at or past it, ``m7_skew``'s search is at the edge of its
range and the angle is an artefact of the search rather than a measurement, so
rotating by it can leave the image *less* upright than it was.  In that case
the image is returned as it arrived -- the same object, not a copy -- because
a working image that was not corrected is still a working image, and 4.13
already requires the detector to report "no MRZ" rather than raise.  An image
with no text in it at all lands in the same branch, because the scan
estimator's answer for a blank frame is the end of its own search range.

**The input is a three-channel BGR image, because that is what ``m7_skew``
takes.**  Inheriting the contract rather than widening it is the point: a
helper that quietly converted a greyscale frame first would be running the
estimator on something its author never saw, and the conversion would be the
one step in Part 4 nobody could check against the quality gate that ran
before it.  ``app.analysis`` decodes uploads with ``IMREAD_COLOR`` for the same
reason.

**The cut in 4.2 is a local one, and the measurement that decided it is a
photograph rather than a scan.**  4.1 filled the new corners with the image's
own median colour precisely because it could not assume the paper was white,
and a single threshold across the page inherits that same wrong assumption:
on a page whose right-hand half is at half brightness, one global cut -- Otsu,
the estimator ``m7_skew`` itself reaches for -- calls **88%** of that half ink
and hands 4.3 a connected component **264 pixels** wide.  The local cut calls
**2.9%** of the whole page ink, which is what the same page scanned flat gives
(2.9%), and its widest component is one glyph, 22 pixels.  So the choice is
measured rather than preferred, and the test says both halves of the
comparison: a helper that swapped the local cut for a global one would have to
pass a page where the shadowed half is mostly white.

**Inverted, so the glyphs are the white.**  4.3 numbers connected components,
4.4 filters them by height and 4.5 groups them into lines, and all three read
"ink" as "the thing to look at".  ``connectedComponentsWithStats`` treats the
zero-valued region as background and numbers it first, so putting paper at 0
and glyphs at 255 makes the component list 4.3 reads *be* the glyph list, with
the page itself in the one entry it can throw away.  The other way round hands
4.3 a single full-page foreground component to reject.

**The offset is not zero, and that is arithmetic rather than taste.**
``THRESH_BINARY_INV`` marks a pixel white when it sits at or below
``local mean - C``, so with ``C = 0`` a *uniform* page compares equal to its
own neighbourhood mean and every one of its pixels becomes ink: measured, 84%
of the flat fixture is white at ``C = 0`` against 2.9% at the value used here.
The offset is also what stops sensor grain from running the page white -- on
the fixture with sigma-6 grain the ink fraction is 40% at ``C = 0`` and 3.0%
here, within 5% of the clean page's 2.9%.

**``ADAPTIVE_C`` is this project's own number, and what it risks is written
down rather than claimed away.**  Nothing in this repository can say how much
darker than the paper a genuine MRZ stroke is: it holds no copy of Doc 9303
and no printed specimen, and the fixture here is *drawn*, so its strokes are
255 levels below the paper by construction.  A larger offset buys cleaner
paper at the cost of faint print; a smaller one lets speckle back in.  The
number is therefore sized to stop the page turning white -- the failure that
makes 4.3 see one component -- and not to reach a clean component list, which
is 4.4's height band's job and not this function's.

**The block size is a rule rather than a tuned optimum, and it was measured
before it was chosen.**  Every odd block from 11 to 61 gives the same reading
on the fixture: the ink fraction moves between 2.6% and 3.0% and the tallest
component is 15 pixels at every one of them.  So the constant is pinned on
three rules, all of them checkable and all of which 41 satisfies -- odd,
because OpenCV refuses an even neighbourhood; **at least twice a glyph**, or
the window is small enough to measure the glyph's own level and stops being a
cut relative to the paper; and **under a line pitch**, or a pixel in the gap
between two MRZ lines takes both lines' ink into its mean.  The sizing those
rules rest on (a 15-pixel glyph, a 70-pixel pitch) is this fixture's, which is
the honest limit of the claim: 4.14 replaces this fixture with a generator, and
the rules are what that generator has to keep satisfying.

**``to_gray`` is idempotent, and that is not what ``deskew`` does on purpose.**
``deskew`` refuses a one-channel frame because it would be running
``m7_skew``'s estimator on something its author never saw.  Here the
conversion *is* the job, so a frame that has already been converted is handed
straight back -- the same object, not a copy, as ``deskew`` does -- and a
caller never has to track how many channels it is holding.  The conversion is
weighted luma rather than the mean of three channels: red reads 76, green 150
and blue 29, where a channel mean says all three are 85.  That is not a
tidiness preference -- a mean treats a saturated blue and a saturated red as
the same brightness, so blue ink or a red security tint lands exactly where
black belongs.

**Neither step moves the frame, which is the second half of 4.1's promise.**
4.1 declined to enlarge the canvas so that a region would mean the same pixel
before and after the rotation; a crop, a resize or a pad here would undo that
for every polygon 4.8 emits and every field box 4.12 returns.  Both functions
are per-pixel or per-neighbourhood, so there is nothing in either that needs
the grid underneath it to change.

**A colour frame handed to ``binarize_inverted`` is a caller's mistake, and it
is not papered over.**  OpenCV answers it with a ``cv2.error``, the same
escape 4.1 documented for ``deskew`` and for a related reason: this function
reads a frame the caller already holds rather than measuring one, so
converting quietly would hide a mistake in the caller behind an answer that
looked fine.  The two functions are separate so that the channel question is
settled in ``to_gray``, where the answer is known, rather than guessed at here.

**4.3 numbers the blobs, and every number it reports is a measured pixel
count rather than a normalised one.**  4.4 writes a height band and 4.10
writes a column segmentation, and neither is checkable against the frame the
officer is looking at unless the heights here are the pixel heights 4.2
measured -- this fixture's tallest component is 15 pixels and its widest is
22, and 4.4's band has to sit near those.  Normalising by the image height, or
by the median blob, would make 4.4's one constant depend on the capture and put
the two tasks' measurements out of step.

**The background is label 0, and it is dropped by label rather than by
size.**  4.2 put the paper at 0 and the glyphs at 255 precisely so that this
function's list would be the glyph list with the page in the one entry to
throw away.  Every other way of throwing it away fails on the page 4.2
documented: when the page turns white the frame is entirely ink, and OpenCV
numbers the *empty* background anyway, giving that empty label a row in
``stats`` of ``[-1, 2147483647, 0, 0, 0]``.  Dropping the widest component, or
the last one, or the one with the largest area, would drop the single
full-page blob and report a clean page on the one frame where the cut has
failed.  Dropping index 0 leaves that blob visible, which is what 4.4 needs in
order to reject it.  Measured: an all-ink frame gives exactly one component,
600 by 300.

**``CONNECTIVITY`` is 8, and 4 would cut glyphs in half.**  MRZ strokes are
diagonal -- the leg of a ``7``, the crossbar of a ``4``, the shoulder of a
``2`` -- and a diagonal pixel run is 8-connected and not 4-connected.
Measured on a twelve-pixel diagonal stroke: twelve components under
4-connectivity, one under 8.  The cost of 8 is the opposite mistake, two
neighbouring glyphs whose corners touch reading as one blob, and that is 4.4's
and 4.10's problem to live with rather than this function's: this fixture's 51
components come from 53 printed characters, so two have already merged at the
cut, and 4.10 has to segment those whether or not a line is drawn under them
here.

**The connectivity is passed by keyword, because the second positional
argument is not the connectivity.**  OpenCV's own signature reads
``connectedComponentsWithStats(image[, labels[, stats[, centroids[,
connectivity[, ltype]]]]])``, so a call written ``(binary, 8)`` binds the 8 to
the ``labels`` *output* and silently gets the default.  The default happens to
be 8, which is exactly why the mistake is invisible: measured, the positional
form answers a 4-connected and an 8-connected question with the same single
component on a diagonal stroke, where the keyword form answers twelve and one.
Naming the argument is the whole cost of not depending on that.

**The list is ordered down the page and then across it, which is not the
order OpenCV hands back.**  ``connectedComponentsWithStats`` numbers labels in
raster-scan order of each component's first pixel, and that is an artefact of
the labelling algorithm rather than a reading of the page: measured on this
fixture, the fourteenth component's box starts at row 107 and the fifteenth's
at row 106.  4.5 groups by vertical overlap and 4.10 segments along x, so the
order those two want is the one given here, and a test asserts it rather than
assuming it.

**What a glyph can be is two bands, and both of them are in the pixel counts
4.3 measured rather than in fractions of the page.**  A fraction of the page
height would be a different band on every capture and would put this step's
answer out of step with the numbers it is given; measured on the three clean
captures this repository's fixture produces, a glyph is **13 to 15 pixels
tall** with a width-to-height ratio of **0.29 to 1.47**, and the four
constants are sized around those readings rather than around the page.

**Height is the first half and it is the half that does the work on the two
blobs a document frame actually contains.**  A photo region cut out of a
printed page comes through at **180 by 120** -- measured, on a page carrying
a flat-toned photo box -- and its aspect ratio of 1.5 sits *inside* the aspect
band, so nothing but the height bound rejects it.  A signature comes through
as one blob **150 by 20**, whose height sits *inside* the height band, so
nothing but the aspect bound rejects it.  The two negative cases the task
names are therefore rejected by different halves of the same rule, and each
test asserts the other half would have kept it, so neither passes by accident.

**The four constants are held to rules, not to the fixture's numbers, and the
rules are the durable part.**  The height floor is at least half the tallest
glyph measured -- half, because the smallest thing a local cut leaves standing
is a speckle one or two pixels tall, and half is where a mark stops being one;
the height ceiling is under **half the line pitch**, because a glyph taller
than the gap between two baselines would collide with the line above it, and
under that because 4.5 groups by vertical overlap and a blob spanning two
lines would be a group of one.  The aspect floor is a fifth, and the narrowest
character an MRZ prints is a ``1``: a mark five times taller than it is wide
is a rule, a scratch or a fold.  The aspect ceiling is under three, and three
is generous rather than tight -- a Doc 9303 character cell is about square, so
even a pair of merged neighbours is nearer 2:1 than 3:1, while a signature's
stroke measures **7.5** on this fixture.

**The blank page is rejected here rather than upstream, and that is the point
of the ceiling.**  When 4.2's cut loses the page the frame is entirely ink and
4.3 returns exactly one component, **600 by 300**; the height band sits above
the fixture's 15 pixels and below that, so the one frame where nothing was
detected cannot reach 4.5 as a single enormous glyph.  **A greyscale frame
handed to 4.3 is only partly cured by this**, and the number is a test rather
than a caveat: skipping :func:`binarize_inverted` gives 24 components, the
600-pixel page among them, and **6 survive the band** -- every one of them a
5-or-6-by-10 speck of the *paper* rather than of the print, shorter than the
shortest glyph the fixture drew and therefore not separable by a band.  A
caller that gets partial instead of total is the worse of the two failures, so
the honest fix is still 4.2's cut, not a threshold here.

**Nothing here filters on area, and the band does not need one.**  A height and
an aspect ratio already separate every blob this fixture produces; the case
for needing a third threshold would be a *photograph whose texture survives
the cut as glyph-sized fragments*, and the answer to that is
``ADAPTIVE_C`` and ``ADAPTIVE_BLOCK_SIZE`` doing their job rather than a new
number here.  The two sides are pinned from both ends by a test: a 3-by-13
hairline of **39 pixels** is kept, and a photo box of **21,600** is refused
with a fraction of that ink drawn, so a filter on area would get at least one
of them wrong in whichever direction it chose.

**Sharing rows is what makes a line, and the edge that decides it is
half-open.**  A blob joins the line above it while its own top is *strictly*
above that line's running lower edge; a blob whose top sits exactly on that
edge shares no row with it and starts a new line.  The boxes are half-open
for :class:`MrzComponent`'s own reason -- ``binary[top:top + height,
left:left + width]`` is exactly the blob -- and the same half-open edge is
what makes this boundary decidable rather than a matter of taste.
Measured on this fixture: the two lines are rows **105 to 120** and **175 to
190**, and the **55 rows** between them are what any grouping rule has to
leave alone.

**A line is closed by the running maximum of its members' lower edges, so
membership is transitive, and that is what "the same line" has to mean.**  A
glyph whose descender hangs below its neighbours is still printed on their
baseline, so a rule that compared each blob only against the *previous* one
would cut such a line in two -- silently, because both halves would go on to
look like glyphs.  A blob is therefore compared against the deepest thing in
the line being filled, which is also the reading that makes 4.4's ceiling
load-bearing: that ceiling sits under half the line pitch precisely so that
no surviving blob can bridge two baselines and pull a whole line into a
group of its own.

**Lines read down the page and the glyphs inside a line read across it, and
neither order is the one 4.3 chose.**  Groups come back top to bottom because
4.7 counts lines and 4.11 maps a cell index to a field offset, so which group
is line 1 is a question with a wrong answer; members come back left to right
because 4.10 segments along x and its cell 0 has to be the leftmost character.
4.3's order is down the page and then across it, which is the raster-scan
order of the *labelling* rather than the reading order of the document:
measured, the lefts of the 24 glyphs on this fixture's first line are not
monotonic in 4.3's order.  Re-sorting is what turns 4.3's list into text.

**Nothing is discarded here and nothing is re-measured.**  A group of one
comes back as a group of one, because "is this line plausible" is 4.6's
question and answering it here would be a threshold 4.4 did not write down --
the same argument :func:`filter_glyphs`'s own band makes.  The six specks of
*paper* a greyscale frame leaves behind survive 4.4 for exactly that reason
and come back here as **two lines of 2 and 4**, sitting on the same two
baselines the print does (measured, rows 108-118 and 178-188).  This step
reports the grouping it was handed rather than to pre-judge it, and 4.6's own
measurement is that **its two scores do not throw those specks away**: they
are ten rows tall like each other and seventy rows apart like each other,
which is all a consistency score can see.  What a line of two blobs is
caught by is 4.7's cell count, and what a caller that produced it has to fix
is 4.2's cut.  The records that come back are the ones that went in, for
4.4's reason, and a caller may hand this function anything at all -- in
practice :func:`filter_glyphs`'s output, but nothing here re-applies the
band.

**4.6's two scores are both measured against the groups themselves, because
the alternative is a number nobody wrote down.**  A height score compared
against a constant would be a fifth glyph-size threshold in a module that
already holds four, and a spacing score compared against a constant would be
a number of a kind this repository cannot source at all: it holds no copy of
Doc 9303 and no printed specimen, so nothing here can say how far apart two
lines of MRZ sit on a page.  So both are *ratios taken on the group*: how
far the line's own glyph heights spread about its own median, and how far the
spacing between this line and its nearest neighbour departs from the leading
the set itself shows.  The first has real numbers on both sides of it --
measured on the four captures 4.2 builds, the worst line spreads **2 rows on
a median of 14** (0.14), and the band leaves more than twice that again.
The second has **one** reading to be sized from: all four captures give a
leading of exactly **70** and nothing else, because the fixture has two lines
and no third.  So the spacing band is held to a rule and written down as a
starting point -- a quarter of the leading, which at 70 rows is **17.5**,
more than the tallest glyph on the page (15): a departure smaller than a
glyph cannot be told from a printing or a scanning artefact, and one larger
than a glyph is a different line of type.

**The leading a set shows is its own tightest spacing, and a line is judged
on the nearest of its two spacings.**  The lines of one MRZ are set on one
leading, so the closest two are the best evidence of what it is, and a group
whose spacing to *every* neighbour departs from that is not on it.  Judging
on the nearest spacing is what lets a chain of lines on one leading survive
end to end, and it is also what stops a stray line taking a real line down
with it: a rule that scored the *pair* would have had to discard both members
of a mismatched pair, and one of them is an MRZ line.

**What these two scores do not catch is written down rather than left to be
discovered.**  Two groups have one spacing between them, so with two lines
the spacing score cannot reject anything at all -- arithmetic rather than a
threshold, and the reason the task's own test needs a third line.  A stray
line printed *within* a quarter of the leading is consistent with the set and
survives (measured: 0.14, on a page carrying a name line 25 rows above the
MRZ), and so does one printed tighter than the leading, which is what a line
caught between two MRZ lines looks like.  Neither is separable from a genuine
third line by a consistency score; 4.7's line count and 4.10's cell count are
what a page with three lines on it has to answer to.

**A line is all-or-nothing here, and that is the task's own wording.**  One
member a third off the line's own median discards the line with it, and 4.10
is the reason that is the right way round: keeping the rest would hand the
cell segmentation a cell for a mark the cut invented, which is a worse
failure than losing a line a re-scan would find again.  **4.14 replaces this
fixture with a generator that prints three lines, and both bands have to be
re-derived from that page rather than from these readings.**

**4.7 asks what shape the set has, and the shape is read from Part 3 rather
than written down here.**  A TD1 is three lines of 30 characters, a TD2 two
of 36 and a TD3 two of 44, and :data:`app.pipeline.tier0.document.MRZ_SHAPES`
is already the one place in this project that states all three together --
the same three constants, resolved rather than retyped, because a table
written a second time is a table that can disagree.  So this is the first
import a sibling *format* module gets in this file, and it costs nothing:
``document``, ``td1``, ``td2`` and ``td3`` load neither ``cv2`` nor
``numpy``, so the property the module docstring opens with still holds.  **A
fourth format is one row in that table** and nothing here changes, which is
the argument the table's own docstring makes and this step inherits.

**The line count is exact and the glyph count is a band, and the two halves
are different questions.**  A zone is three lines or it is not: a TD1 is
three lines *because* the name has a line of its own, and a fourth line or a
missing one is a different document rather than a damaged reading of this
one, so there is nothing to score the count against.  The width is different,
because a cut is not a character counter: 8-connectivity merges two glyphs
whose corners touch and a broken stroke at a faint threshold splits one, so
the blob count of a line is near the character count rather than equal to it.
Measured on this fixture's own page at its own size, the three specimen
zones come back as **30, 35.5 and 43** blobs per line against nominals of
30, 36 and 44 -- a worst departure of **1**, and never a line that is long
rather than short, because the merge is the ordinary failure at this cut.
**A band of :data:`LINE_LENGTH_TOLERANCE` covers that with a row in hand,
and exact equality would refuse two of the three real formats on the
repository's own measurements.**

**The band is the largest one that leaves no glyph count inside two formats
at once, and that is a property of the table rather than of this fixture.**
The three line lengths are 30, 36 and 44, so the closest two are **6** apart
and a band wider than **3** would put some count inside two shapes and make
the answer depend on the order :data:`MRZ_SHAPES` is walked.  A band of 2 is
under that ceiling and over the measured departure, and a test walks every
count from 0 to 60 to show no median can reach two formats.  **The band is
symmetric** -- a split glyph pushes the other way and is not a rarer failure
on a faint capture than a merge is on a tight one -- and **re-derive it from
27.1's corpus, not from these readings**; the rule that outlives the number
is the unambiguity ceiling, the way 4.4's and 4.6's rules outlive theirs.

**"No MRZ here" is an answer this step can give, and it is the one 4.13
needs.**  The answer is the name a set of lines *has the shape of* or
``None``, never the nearest shape: a set of two lines holding 26 blobs each
is 4 away from a TD1 and 10 from a TD2, and neither is a document this
project has a parser for.  A detector that always picked the closest of the
three would name a format for every frame it was handed, including the blank
ones -- and a visa read as a passport shifts every field, which is the
expensive direction to be wrong in.

**What this step catches is the line of two blobs 4.5 and 4.6 could not.**
The specks a greyscale frame leaves behind arrive as two lines of 2 and 4,
all ten rows tall like each other and a leading apart like each other, and
both of 4.6's scores pass them because a consistency score cannot tell a line
of two blobs from a line of forty.  Their **median of 3** is the thing that
cannot be a format, and the count does the other half of the work: three
lines whose median is exactly 44 is a TD3 by width and no MRZ by shape,
because no format has three lines of anything.

**Nothing else is re-opened, and the median is over the lines that
survived.**  4.4 decided what a glyph is and 4.6 decided which lines are
worth reading; this step reads neither, so a blob that failed 4.4 and a
line that failed 4.6 are not arguments here.  The median rather than the mean
is what makes a half-read line survivable: a TD1 whose third line came back
as four blobs has a median of 30 and a mean of 21, and 4.10's cell count is
the check that the four blobs are not a line.
"""

import dataclasses
import statistics

import cv2
import numpy as np

from ...quality_checker import m7_skew
from . import document

__all__ = [
    "MAX_DESKEW_DEG",
    "MrzComponent",
    "binarize_inverted",
    "deskew",
    "extract_components",
    "filter_glyphs",
    "filter_lines",
    "group_lines",
    "infer_format",
    "skew_deg",
    "to_gray",
]


#: The largest angle ``deskew`` will act on, which is the angle at or past
#: which ``m7_skew``'s own quality verdict is already a failure.  Bound to the
#: constant rather than restated, so the helper and the gate cannot disagree
#: about what "too rotated" means.
MAX_DESKEW_DEG = m7_skew.MAX_SKEW_DEG

#: Side of the square neighbourhood the local mean is taken over, in pixels.
#: Must be odd -- OpenCV refuses an even one -- and the module docstring gives
#: the other two rules it is held to and how each was measured.
ADAPTIVE_BLOCK_SIZE = 41

#: How far below its own neighbourhood a pixel must sit to be called ink.
#: Zero is not the neutral choice it looks like: the comparison is "at or
#: below", so a uniform page at ``C = 0`` is entirely ink.  See the module
#: docstring for what a larger number would cost.
ADAPTIVE_C = 10


#: Whether two blobs that touch only at a corner are one blob or two.  8, and
#: the module docstring gives the measurement that chose it over 4 -- an MRZ
#: stroke is diagonal, and 4-connectivity reads a twelve-pixel diagonal as
#: twelve glyphs.  A module constant rather than an argument for the reason
#: ``ADAPTIVE_C`` is: a caller cannot label the page's own definition of
#: "connected" differently from the one 4.4 filters on.
CONNECTIVITY = 8


#: How short a blob may be and still be a character, in pixels.  At least
#: half the tallest glyph 4.3 measured, and below the shortest one: half is
#: where a mark left by the cut stops being a speckle, and the band is a
#: *pixel* count for the reason 4.3's record is -- a fraction of the page
#: height would be a different band on every capture.
GLYPH_MIN_HEIGHT_PX = 8

#: How tall a blob may be and still be a character, in pixels.  Above every
#: glyph on this fixture, and under half the line pitch: a glyph taller than
#: the gap between two baselines would collide with the line above it, and
#: 4.5 groups by vertical overlap, so a blob spanning both lines would be a
#: group of one.  Measured: 300 for a page whose cut went white.
GLYPH_MAX_HEIGHT_PX = 24

#: Narrowest width-to-height ratio a character can be.  A fifth, and a fifth
#: because the narrowest thing an MRZ prints is a ``1``: a mark five times
#: taller than it is wide is a printed rule, a scratch or a fold.
GLYPH_MIN_ASPECT = 0.2

#: Widest width-to-height ratio a character can be.  Under three, and three
#: is generous rather than tight: an MRZ character cell is about square, so
#: even a pair of merged neighbours is nearer 2:1, while a signature's stroke
#: measures 7.5 on this fixture.
GLYPH_MAX_ASPECT = 2.5


#: How far a line's own glyph heights may spread, as a fraction of that
#: line's median glyph height.  A third, and a third because a line is set in
#: one body size: 4.4's band judges each blob on its own and spans 8 to 24
#: rows around a median of 15, so a line holding one ten-row speck among
#: fifteen-row glyphs is a line 4.4 could not refuse and this can.  The
#: module docstring gives the measured worst case and the rule that makes
#: this a ratio rather than another pixel count.
LINE_MAX_HEIGHT_SPREAD = 1 / 3

#: How far the spacing between two lines may depart from the leading the set
#: itself shows, as a fraction of that leading.  A quarter, and a quarter
#: because it is a *ratio*: a page photographed at another scale, or drawn by
#: 4.14's generator at another resolution, gives the same answer.  The
#: module docstring is honest that this band has a single measurement behind
#: it and is held to a rule until there are three lines to measure.
LINE_MAX_SPACING_SPREAD = 0.25


#: How far a line's glyph count may sit from the character count its format
#: prints and still be that format, in glyphs.  Two, for the two rules the
#: module docstring gives it: over the departure this cut actually shows
#: (measured, the three specimen zones read 30, 35.5 and 43 against 30, 36
#: and 44), and under half the distance between the two closest line lengths
#: (6 apart, so 3 is the ceiling) -- because a count inside two shapes at
#: once would make the answer depend on the order the table is walked.  It is
#: symmetric, since a split glyph pushes the other way.  A constant rather
#: than an argument for ``ADAPTIVE_C``'s reason: one detector, one number.
LINE_LENGTH_TOLERANCE = 2


def _border_fill(image):
    """The colour the four new corners get: the median of the pixels present.

    Returned as a **tuple**, and that is not a style choice.  OpenCV reads a
    scalar ``borderValue`` as ``(v, 0, 0)`` on a three-channel image, so
    ``borderValue=255`` fills a white page's corners blue -- corners that
    binarise as ink and hand 4.3 a full-width false component.  One channel
    per channel, always, is what keeps the fill invisible downstream.
    """
    return tuple(
        int(round(float(value))) for value in np.median(image.reshape(-1, 3), axis=0)
    )


def skew_deg(image, mode="scan"):
    """The signed angle ``m7_skew`` reads for this image, in degrees.

    Re-exported rather than recomputed, so that "what angle is this image at"
    has one answer in this project.  A positive angle is the one that undoes
    the current tilt: an image rotated by ``+5`` degrees reads about ``-5``
    here, and rotating by what this returns is what puts it back.

    ``None`` means ``m7_skew``'s text-block estimator found no text at all.
    The scan estimator never returns ``None``; see the module docstring for why
    its number still has to be bounded before anyone acts on it.
    """
    return m7_skew.text_skew(image, mode=mode)


def deskew(image, mode="scan"):
    """Return ``image`` rotated upright by the angle ``m7_skew`` measured.

    Same size, same dtype, same coordinate frame as the argument -- see the
    module docstring for why the frame is the thing being protected, and
    ``image`` is three-channel BGR for the reason given there.  When the angle
    is one this helper will not act on, the argument is returned **as it
    arrived** -- the same object, not a copy -- so a caller can tell "nothing
    was wrong" from "this made a copy" without comparing pixels.
    """
    angle = skew_deg(image, mode=mode)
    if angle is None or abs(angle) > MAX_DESKEW_DEG:
        return image

    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), angle, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=_border_fill(image),
    )


def to_gray(image):
    """The frame as one channel of weighted luma, at the same size.

    The step :func:`deskew` could not take, for the reason its docstring and
    the module's give: ``m7_skew`` wants three-channel BGR, so the conversion
    belongs here, after the rotation rather than before it.

    A frame that is *already* single-channel is handed back as it arrived --
    the same object, not a copy, exactly as :func:`deskew` reports "nothing
    was wrong" -- so a caller that runs the pipeline twice, or that receives
    an already-converted frame from somewhere else, does not have to track
    how many channels it is holding.

    Weighted luma, not the mean of the three channels: red reads 76, green
    150 and blue 29, and a mean says all three are 85.  See the module
    docstring for why that difference is about a document rather than about
    tidiness.
    """
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def binarize_inverted(gray):
    """The ink as 255 and the paper as 0, cut locally.

    ``gray`` is one channel, from :func:`to_gray` or from anywhere else that
    produces one.  A three-channel frame here is a caller's mistake and comes
    back as a ``cv2.error`` rather than a quiet conversion -- see the module
    docstring.

    Same height, same width, same coordinate frame as the argument, for the
    reason 4.1 gave and the module's repeats: a region has to mean the same
    pixel all the way down to 4.12.

    The threshold is adaptive and inverted, and the two constants that say so
    are the module's rather than this function's arguments: a caller cannot
    pass an even neighbourhood or an offset of zero by accident, and cannot
    end up with two different pages binarised two different ways.
    """
    return cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        ADAPTIVE_BLOCK_SIZE,
        ADAPTIVE_C,
    )


@dataclasses.dataclass(frozen=True)
class MrzComponent:
    """One blob of ink, measured.  What :func:`extract_components` returns.

    **Every field is a measured pixel quantity, never a normalised one.**  The
    reason is the module docstring's: 4.4 writes a height band against these
    numbers, and a height divided by the page height would be a different
    number on every capture, so the band and the measurement could not be
    checked against each other.

    :attr:`left` and :attr:`top` are the box's own corner and :attr:`width`
    and :attr:`height` its own extent, so :attr:`bbox` is derived from them
    rather than stored beside them -- one set of numbers, and no way for a box
    to disagree with its own parts.

    **The box is half-open, so ``binary[top:top + height, left:left + width]``
    is exactly this component and nothing else.**  OpenCV's own ``cv::Rect``
    counts its far edge in, which makes a one-pixel blob the box
    ``(6, 4, 6, 4)``; the half-open form makes it ``(6, 4, 7, 5)``, and that
    is the form 4.8's polygon and 4.12's field box are cut from, because a
    numpy slice of the frame is what a caller will actually write.

    **The centroid is the mean of the component's own pixels, not the middle
    of its box.**  Those differ for every blob that is not solid, and an MRZ
    glyph is a collection of strokes rather than a rectangle: measured on an
    L-shaped blob the centroid is ``(7.333, 4.167)`` where the box centre is
    ``(7.0, 5.0)``.  4.9 fits a line through these to find the residual skew
    inside a line, and a box centre would tilt that fit towards whatever glyph
    shape happened to be in the group.

    :attr:`area` is the blob's pixel count.  It is carried because it is one
    of the five numbers the cut already produced, and **not** because anything
    filters on it: 4.4's band is height and aspect ratio, and the case for
    needing an area filter as well is written down in the handover as two
    constants having been asked to do 4.4's job.

    **Frozen, for the reason :class:`~app.pipeline.tier0.td3.MrzDocument` is.**
    A record that could be edited would let a measured glyph become a
    convenient one, which is the same failure as a parse that repaired a check
    digit to make its own verdict pass.
    """

    left: int
    top: int
    width: int
    height: int
    area: int
    cx: float
    cy: float

    @property
    def bbox(self):
        """``(left, top, right, bottom)``, half-open -- see the class docstring."""
        return (self.left, self.top, self.left + self.width, self.top + self.height)

    @property
    def centroid(self):
        """``(cx, cy)`` as one point, which is the form 4.9 fits a line through."""
        return (self.cx, self.cy)


def extract_components(binary):
    """The ink of ``binary`` as a tuple of measured :class:`MrzComponent`.

    ``binary`` is one channel from :func:`binarize_inverted`, in the frame the
    argument is already in -- no crop, no resize, no pad, for 4.1's reason:
    every polygon 4.8 emits and every field box 4.12 returns is a set of
    coordinates in this frame and nothing downstream carries an offset.

    **The page is the one entry dropped, and it is dropped by label.**  The
    module docstring gives the measurement -- an all-ink frame leaves the
    empty background holding the sentinel row ``[-1, 2147483647, 0, 0, 0]``,
    so dropping by width, by area or by position would discard the one
    full-page component that 4.4 exists to reject.

    **Nothing is filtered here, and that is 4.4's job rather than a gap.**
    Measured on this repository's own fixture: a clean page gives 51
    components and a sigma-6 grainy one gives 313, with areas from 48 pixels
    down to a single pixel, while the widest and the tallest component are
    identical on both.  A function that dropped the speckle here would be
    doing 4.4's height band with a threshold nobody wrote down, and the test
    that says so is what stops it.

    The numbers come out of the labelling rather than being recomputed from
    the label image, and they are converted to plain ``int`` and ``float`` on
    the way: 4.4 compares them against a band, 4.5 sorts them, and a record
    carrying ``numpy.int32`` is one that cannot be put in a JSON body when
    4.13's empty result becomes a response.

    A three-channel frame is a caller's mistake and comes back as a
    ``cv2.error``, for 4.2's reason.  A *greyscale* frame is a different
    mistake and is not caught, because catching it would mean a ``raise`` this
    module may not have: OpenCV reads every non-zero pixel as ink, so
    :func:`to_gray`'s own output handed straight in gives 24 components on
    this fixture with one of them 600 pixels wide.  That is the page-turned-
    white failure reached by a different route, and the honest way to refuse
    it is a binarisation step that guarantees the input -- which is
    :func:`binarize_inverted`.
    """
    count, _, stats, centroids = cv2.connectedComponentsWithStats(
        binary, connectivity=CONNECTIVITY
    )

    components = [
        MrzComponent(
            left=int(row[cv2.CC_STAT_LEFT]),
            top=int(row[cv2.CC_STAT_TOP]),
            width=int(row[cv2.CC_STAT_WIDTH]),
            height=int(row[cv2.CC_STAT_HEIGHT]),
            area=int(row[cv2.CC_STAT_AREA]),
            cx=float(centroids[label][0]),
            cy=float(centroids[label][1]),
        )
        for label, row in enumerate(stats)
        if label
    ]
    components.sort(key=lambda component: (component.top, component.left))
    return tuple(components)


def filter_glyphs(components):
    """The blobs from :func:`extract_components` that a character could be.

    Two bands and nothing else: a **height** band in the pixel counts 4.3
    measured, and an **aspect-ratio** band on top of it.  The module docstring
    gives the readings the four constants are sized from and the rules they are
    held to; the two are not the same thing on purpose, because 4.14 replaces
    this fixture and only the rules survive that.

    **Height is tested first, and that ordering is the load-bearing part.**
    A photo region measures 180 by 120 on the page this fixture is built on --
    an aspect ratio of 1.5, comfortably inside the aspect band -- so it leaves
    on its height.  A signature measures 150 by 20, comfortably inside the
    height band, and leaves on its aspect.  Whichever half runs second cannot
    change either answer, and each test asserts the other half alone would have
    kept the blob.

    **Nothing here reads :attr:`~app.pipeline.tier0.mrz_region.MrzComponent.
    area`, and that is measured rather than promised.**  A 3-by-13 hairline of
    39 pixels is kept and a photo box holding a fraction of its 21,600 is
    refused; a third threshold on area would get one of the two wrong in
    whichever direction it was written, and the case for needing one at all is
    ``ADAPTIVE_C`` and ``ADAPTIVE_BLOCK_SIZE`` doing 4.4's job.

    **The records that survive are the ones that came in, not copies of them.**
    4.5 groups them and 4.9 fits lines through their centroids, so a rebuilt
    record would be a second measurement of the same blob and a second thing
    to keep in step; the order 4.3 chose is preserved, because the group and
    the segmentation both read down the page.

    A record of zero height cannot come out of :func:`extract_components`, but
    a caller can hand one over: it fails the height bound first, so the aspect
    ratio is never divided by zero.
    """
    return tuple(
        component
        for component in components
        if GLYPH_MIN_HEIGHT_PX <= component.height <= GLYPH_MAX_HEIGHT_PX
        and GLYPH_MIN_ASPECT <= component.width / component.height <= GLYPH_MAX_ASPECT
    )


def group_lines(components):
    """The blobs that share rows, as one tuple of lines down the page.

    In practice the argument is :func:`filter_glyphs`'s output, but nothing
    here re-applies that band -- 4.4 decided what a glyph is and this step's
    question is a different one, which blobs share rows.  Deciding it twice
    would be a threshold nobody wrote down, which is the argument
    :func:`filter_glyphs`'s own band makes.

    **The outer tuple is down the page and each inner tuple is across it.**
    4.7 counts the groups and 4.11 maps a character cell to a field offset, so
    which group is line 1 has a wrong answer; 4.10 segments a line along x, so
    cell 0 has to be the leftmost character in it.  4.3's own order is the
    raster-scan order of OpenCV's labelling rather than the reading order of
    the document, so it is re-sorted here rather than inherited.

    **A blob joins the line above it while its top is strictly above that
    line's deepest member, which makes membership transitive.**  A glyph
    hanging below its neighbours is still on their baseline, so comparing
    each blob only against the previous one would split such a line without
    anything downstream being able to tell.  A blob whose top sits exactly on
    the running lower edge shares no row with it and starts a new line: the
    half-open edge is the same one :class:`MrzComponent`'s box is, so the
    boundary is decidable rather than a matter of taste.

    **Nothing is discarded and no record is rebuilt.**  A group of one comes
    back as a group of one -- that is 4.6's call, and it is measured rather
    than promised here: the specks a greyscale frame leaves behind arrive as
    two lines of 2 and 4, on the same baselines the print uses.  The records
    that come back are the ones that went in, so 4.9's fit through their
    centroids and 4.8's polygon are still working from 4.3's own
    measurement.

    An empty input is ``()`` rather than an error, exactly as
    :func:`filter_glyphs` returns ``()`` for it: 4.13 has to be able to say
    "no MRZ here", and the page whose cut went white arrives with nothing to
    group.  A record of zero height -- which :func:`extract_components`
    cannot produce, though a caller can -- has an empty vertical extent, so
    it can only join a line that already reaches past its own top and never
    extends one downwards.
    """
    groups = []
    lower_edges = []
    for component in sorted(components, key=lambda c: (c.top, c.left)):
        if lower_edges and component.top < lower_edges[-1]:
            groups[-1].append(component)
            lower_edges[-1] = max(lower_edges[-1], component.bbox[3])
        else:
            groups.append([component])
            lower_edges.append(component.bbox[3])
    return tuple(
        tuple(sorted(group, key=lambda c: (c.left, c.top))) for group in groups
    )


def filter_lines(lines):
    """The line groups whose glyph heights agree and whose spacing agrees.

    In practice the argument is :func:`group_lines`'s output, and this is the
    first step in Part 4 to discard anything.  **The two scores are ratios
    taken on the groups themselves** -- the module docstring gives the rules
    and the readings -- because a constant to compare against would be a
    fifth glyph-size threshold in a module that already holds four, and the
    spacing one would be a number this repository cannot source at all.

    **Height consistency is a line's own spread about its own median**, so a
    mark the cut invented is measured against the body size of the line it
    landed in rather than against a size 4.4 has already decided.  The median
    is the reference and not the mean, because one odd blob is exactly what
    this is looking for and a mean would be dragged towards it.

    **Spacing consistency is a departure from the leading the set shows**, and
    the leading is the set's *tightest* consecutive spacing, for 4.6's stated
    reason.  A group is judged on the *nearest* of its two spacings, so a
    chain of lines set on one leading survives end to end and a group is
    discarded only when nothing near it agrees.  A group with no neighbour at
    all has no spacing to disagree with and is judged on height alone; with
    exactly two groups there is one spacing between them, so the axis cannot
    reject anything, which is arithmetic rather than a threshold.

    **A line is all-or-nothing, and one mark takes the rest with it.**  The
    task's wording is "discard groups that fail", and 4.10 is the reason that
    is the right way round: keeping the other members would hand the cell
    segmentation a cell for a character the cut invented.

    **The groups that come back are the ones that went in, in the order they
    arrived.**  This is a filter, so a rebuilt group would be a second
    measurement of the same blobs, and 4.9 fits lines through their
    centroids.  The spacing is read between the groups *sorted by their own
    tops*, so a caller that hands the same groups over backwards gets the
    same answer rather than a set of negative spacings.

    A group whose members are all of zero height is discarded rather than
    divided by: :func:`extract_components` cannot produce one, but a caller
    can hand one over, and 4.4 refused that record for the same reason.  An
    empty input is ``()``, as everywhere else in this module.
    """
    groups = tuple(lines)
    tops = [min(component.top for component in line) for line in groups]
    order = sorted(range(len(groups)), key=tops.__getitem__)

    # The nearest spacing each line has to a neighbour, and the tightest
    # spacing anywhere in the set: the leading this group of lines shows.
    spacing_of = {}
    for above, below in zip(order, order[1:]):
        spacing = tops[below] - tops[above]
        for index in (above, below):
            spacing_of[index] = min(spacing_of.get(index, spacing), spacing)
    leading = min(spacing_of.values(), default=0)

    kept = []
    for index, line in enumerate(groups):
        heights = sorted(component.height for component in line)
        median = statistics.median(heights)
        if median == 0:
            continue
        if heights[-1] - heights[0] > LINE_MAX_HEIGHT_SPREAD * median:
            continue
        spacing = spacing_of.get(index)
        if (
            spacing is not None
            and spacing - leading > LINE_MAX_SPACING_SPREAD * leading
        ):
            continue
        kept.append(line)
    return tuple(kept)


def infer_format(lines):
    """The name of the format these line groups have the shape of, or ``None``.

    In practice the argument is :func:`filter_lines`'s output, and this is the
    first step in Part 4 that answers a question about the *document* rather
    than about the ink.  **The answer is the name, or ``None`` -- never the
    nearest shape**, because 4.13 has to be able to say "no MRZ here" and a
    detector that always named one of the three would name a format for every
    frame it was handed, including a blank page.

    **The shapes are read from Part 3, not written here.**
    :data:`app.pipeline.tier0.document.MRZ_SHAPES` already states all three
    together from each format's own constants, so a fourth format is one row
    in that table and nothing in this file changes -- and a width corrected in
    ``td3`` cannot leave this file answering with the old one.

    **The line count is exact and the glyph count is a band, because they are
    two different questions.**  A TD1 is three lines *because* the name has a
    line of its own, so one line short or one line long is a different
    document rather than a damaged reading of this one and there is nothing to
    score it against.  A line's glyph count is near its character count and
    not equal to it: 8-connectivity merges two glyphs whose corners touch and
    a broken stroke at a faint threshold splits one.  Measured on this
    fixture's own page at its own size, the three specimen zones come back as
    **30, 35.5 and 43** blobs per line against nominals of 30, 36 and 44, so
    exact equality would refuse two of the three real formats on this
    repository's own readings and :data:`LINE_LENGTH_TOLERANCE` covers the
    worst departure of 1 with a row in hand.  **The band is under half the
    distance between the two closest line lengths**, so no count is ever
    inside two formats at once and the answer cannot depend on the order the
    table is walked.

    **The median is over the lines that survived, and the median rather than
    the mean.**  A TD1 whose third line came back as four blobs has a median
    of 30 and a mean of 21, and 4.10's cell count is the check that the four
    blobs are not a line -- 4.7 is not going to re-open 4.4's band or 4.6's
    two scores to make that call, because both of them have already had a say
    about which blobs are worth this count.  On **two** lines the median *is*
    the mean, so the two statistics only ever differ on a three-line zone.

    **The count is a count of records, so two blobs at the same place are
    still two.**  4.5 does not guarantee the groups it hands over are evenly
    spaced, 4.10 is what segments along x, and nothing here looks at where a
    record sits -- a line is as many glyphs as it has records.

    The lines' own order is not read, so a caller that hands the same groups
    over reversed or rotated gets the same answer.  An empty input is
    ``None``, as everywhere else in this module, and a line of no glyphs is
    a line of zero rather than an error.
    """
    groups = tuple(lines)
    if not groups:
        return None
    median = statistics.median(len(line) for line in groups)
    for (line_count, line_length), name in document.MRZ_SHAPES.items():
        if line_count != len(groups):
            continue
        if abs(median - line_length) <= LINE_LENGTH_TOLERANCE:
            return name
    return None
