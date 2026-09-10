// Step 3 used to say two contradictory things about the same session.
//
// Opening the trim panel ran its `sync()` once on construction, which seeded a
// *proposed* window of min(dataDur, videoDur) into the same object the header
// was computed from. So a session whose video was twelve seconds longer than
// its data rendered "⚠ Video is 192.00s but data is 179.96s" directly under
// "video 179.96s · data 179.96s · ✓ aligned" -- the second line describing a
// trim nobody had applied, in the words it would use if they had.
const { test } = require('node:test');
const assert = require('node:assert');
const { boot } = require('./harness');

function sessions(trim) {
  const video = { id: 'v1', name: 'dyad02.mp4', duration: 192.0 };
  if (trim) video.trim = trim;
  return {
    sessions: [{
      videoID: 'dyad02',
      video,
      series: [
        { id: 's1', name: 'dyad02_rtpjSync.csv', dataType: 'rtpjSync',
          bounds: { min: 0, max: 180.0 } },
        { id: 's2', name: 'dyad02_headSync.csv', dataType: 'headSync',
          bounds: { min: 0, max: 180.0 } },
      ],
    }],
    ffmpeg_available: true,
  };
}

async function header(trim) {
  const { window, page } = boot({ routes: { '/api/sessions': sessions(trim) } });
  await page.renderAlign();
  const durs = window.document.querySelector('#align-list .align-durs');
  const decision = window.document.querySelector('#align-list .decision-msg');
  assert.ok(durs, 'the align card rendered a header');
  return { head: durs.textContent, decision: decision ? decision.textContent : '' };
}

test('an untrimmed session is not called aligned', async () => {
  const { head, decision } = await header(null);

  assert.match(decision, /Video is 192\.00s/, 'the decision states the real mismatch');
  assert.doesNotMatch(head, /aligned/,
    'the header must not claim alignment while the video is still 12s longer');
  assert.match(head, /192\.00/, 'the header reports the video as it is on disk');
});

test('the header follows the trim once it is applied', async () => {
  const { head } = await header({ start: 0, end: 180.0 });

  assert.match(head, /aligned/, 'an applied trim does make the session aligned');
  assert.match(head, /180\.00/, 'and the header reports the trimmed length');
});
