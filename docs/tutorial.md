# From data to a dashboard

<p class="lede">In this tutorial, we'll use the no-code builder to set up your DIMS dashboard from
  scratch — no programming, no JSON files, no renaming files by hand. Bring <b>your own
  recordings</b>, or press one button for <b>an example study</b> if you don't have any
  yet; either way you'll have a working dashboard by the end. The four analyses DIMS
  can run are at the end of the page, one section each — take them one at a time, or
  not at all.</p>

## The example study

<div class="path builder">
  <h3>ConvoConnect-Mini</h3>
  <p class="sub">Two pairs of strangers, three minutes of conversation each,
    everything synthetic. Step 2 generates it at the press of a button — use it if you
    have no data of your own yet, and to follow the times and values quoted below.</p>
  <p>Each pair — <code>dyad01</code> and <code>dyad02</code> — has the four things
    any DIMS study is built from, all on one clock: <b>a video</b> of the
    conversation, <b>measurements</b> over time, <b>a transcript</b>, and <b>ELAN
    phase codes</b>. That is all the tutorial below needs.</p>
  <p>The measurements are five: the speed of each partner's left and right hand, and
    one belonging to the pair rather than to either of them — <code>rtpjSync</code>,
    how closely their brains are tracking each other. The optional sections at the
    end of this page reach for those: the hands for anything comparing two signals,
    <code>rtpjSync</code> for anything looking at one. It's modelled on the first
    case study in the DIMS paper, where a rise in inter-brain synchrony isn't the
    finding but the <i>question</i>: you go back to the video and the transcript to
    see what kind of moment it was.</p>
  <table class="spec">
    <tr><th>Pair</th><th>What happens</th><th>Why it is in the example</th></tr>
    <tr><td>dyad01</td><td>Two people who click almost immediately.</td>
        <td>Four synchrony peaks, each on a moment you can name.</td></tr>
    <tr><td>dyad02</td><td>A conversation that never gets going.</td>
        <td>Synchrony sits near zero and its biggest peaks land on nothing — and its
          video is <b>12 s longer than its data</b>, so step 3 has something to
          fix.</td></tr>
  </table>
  <p class="muted">None of it is a recording, and none of it ships with the builder:
    the signals, the video and the annotations are generated together from one
    conversation script the first time you ask for them, which is why they agree with
    each other.</p>
</div>

## Before you start

<div class="mini">
  <div><h4>Python 3.10–3.12</h4><p>A free, one-time install from
    <a href="https://www.python.org/downloads/">python.org</a>. On 3.13 everything
    works except motion capture from video.</p></div>
  <div><h4>The repository</h4><p><a href="https://github.com/dims-network/dims">dims-network/dims</a>
    — clone it, or download the ZIP and unzip it.</p></div>
  <div><h4>About 10 minutes</h4><p>Most of it yours; step 6 is about half a minute
    on the basic path. The optional analyses at the end say what they add.</p></div>
  <div><h4>No internet, after the install</h4><p>Everything after the first launch
    runs on your own machine. Your data never leaves it.</p></div>
</div>

## Step by step

<div class="path builder">
  <p class="sub">Here's the whole process, one step at a time.</p>
  <ol class="steps">
    <li>
      <h4>Start the builder</h4>
      <p>Open the <code>apps/builder/</code> folder and double-click the launcher for
        your machine. It installs what it needs the first time — that takes a minute or
        two — and then opens the wizard in your browser.</p>
      <ul>
        <li><b>macOS:</b> <code>run.command</code></li>
        <li><b>Windows:</b> <code>run.bat</code></li>
        <li><b>Linux:</b> <code>run.sh</code></li>
      </ul>
      <div class="callout warn"><b>macOS, first time only:</b> if you see
        <i>“Apple could not verify ‘run.command’ is free of malware.”</i>, click
        <b>Done</b> — not <i>Move to Trash</i> — then open <b>System Settings →
        Privacy &amp; Security</b>, scroll to <b>Security</b>, and click <b>Open
        Anyway</b>. This is macOS flagging any downloaded unsigned script, and it
        happens once.</div>
      <figure class="shot" data-shot="01-wizard-opens.png"
        data-capture="The wizard as it first opens: step 1 selected, the seven step buttons across the top, nothing filled in yet.">
        <img src="../images/walkthrough/01-wizard-opens.png"
             alt="The builder wizard open in a browser at step 1, with the seven steps listed across the top." />
        <figcaption>The wizard opens on step 1. The seven steps across the top are
          the whole job — you can click back to any of them at any time.</figcaption>
      </figure>
    </li>
    <li>
      <h4>Step 1 · Your study</h4>
      <p>Three things to fill in, and one real decision.</p>
      <ul>
        <li><b>Folder</b> — a new or empty folder. The dashboard is created inside it.</li>
        <li><b>Who may see this data?</b> — <b>Private</b> is the default and the right
          answer if you are not certain. It switches on guards that stop recordings
          reaching a shared code repository by accident. <b>Public</b> means the data
          may be published, and adds a workflow that puts the dashboard online.</li>
        <li><b>Dashboard details</b> — a title, optionally a subtitle, authors and a
          contact address. These appear on the finished dashboard.</li>
      </ul>
      <p><b>Playback window</b> is how much video plays either side of the point you
        click. Five seconds is a good starting value; you can change it later.</p>
      <p>Press <b>Create study →</b>.</p>
      <figure class="shot" data-shot="02-your-study.png"
        data-capture="Step 1 filled in: a folder path, Private selected, title 'ConvoConnect-Mini'. Include the visibility explanation under the radio buttons.">
        <img src="../images/walkthrough/02-your-study.png"
             alt="Step 1 of the wizard with a folder chosen, Private visibility selected, and the study title filled in." />
        <figcaption>Private is the default. The note under it says exactly what that
          switches on.</figcaption>
      </figure>
      <div class="callout"><b>Coming back later?</b> Choose <b>Open one I made
        earlier</b> and point it at the same folder. Everything comes back filled in,
        so adding a session or changing an analysis is a rebuild rather than an edit
        of a configuration file.</div>
    </li>

    <li>
      <h4>Step 2 · Sessions &amp; files</h4>
      <p><b>Drag your files onto this screen.</b> Everything from one recording goes
        in together, and the builder works out what each file is from its name and
        its contents:</p>
      <table class="spec">
        <tr><th>What</th><th>Looks like</th><th>Needs to be</th></tr>
        <tr><td><b>A video</b></td><td><code>session1.mp4</code></td>
            <td>One per session. Its name is the <b>session ID</b>, and everything
              else for that recording is named after it.</td></tr>
        <tr><td><b>Measurements</b><br><span class="muted">as many as you have</span></td>
            <td><code>session1_headSpeed.csv</code><br>
              <code>session1_handSpeed.csv</code><br>
              <code>session1_sync.csv</code></td>
            <td><b>One file per measurement</b>, each a column called <code>Time</code>
              (any casing) in <b>seconds</b>, ascending — not milliseconds, not frame
              numbers — plus that one measurement. The part of the filename after the
              session ID is what the measurement gets called, so it is worth naming
              them the way you want to read them. One wide spreadsheet works too; see
              below.</td></tr>
        <tr><td><b>A transcript</b><br><span class="muted">optional</span></td>
            <td><code>session1_transcript.json</code></td>
            <td><code>{ "segments": [ {start, end, speaker, text} ] }</code>, times in
              seconds.</td></tr>
        <tr><td><b>ELAN codes</b><br><span class="muted">optional</span></td>
            <td><code>session1.eaf</code></td>
            <td>Saved from ELAN as usual, with one constraint: only
              <b>time-aligned</b> annotations are drawn. Tiers whose annotations
              hang off a parent annotation rather than off the timeline — symbolic
              subdivisions and associations — are skipped, and an <code>.eaf</code>
              with none of the aligned kind is rejected with a message saying
              so.</td></tr>
      </table>
      <p>The builder groups the files into <b>sessions</b> by that first part of the
        name, and checks each one as it arrives — so a misnamed file or a
        <code>Time</code> column in milliseconds surfaces here rather than as an empty
        tab at the end. Anything it guesses wrong you can fix in place: which session
        a file belongs to, and what the measurement is called.</p>
      <div class="callout tip"><b>Don't have your own data, but want to try DIMS?</b>
        Press <b>Load the example study</b>. The first press takes a few seconds — it
        is generated on your machine rather than shipped — and 16 rows appear: two
        conversations, with their videos, measurements, transcripts and annotations.
        The rest of this page follows that study, so it is also the way to follow
        along exactly.</div>
      <figure class="shot" data-shot="03-sessions-files.png"
        data-capture="The file list after Load the example study: 16 rows grouped under dyad01 and dyad02, each row showing its role and data type.">
        <img src="../images/walkthrough/03-sessions-files.png"
             alt="Step 2 showing sixteen staged files grouped under two sessions." />
        <figcaption>The example study, loaded: sixteen rows across two sessions. Every
          row says what the builder thinks the file is, and you can correct any of
          them.</figcaption>
      </figure>
      <div class="callout"><b>One spreadsheet with several measurement columns</b> is
        also fine — motion tracking usually gives you one. The builder splits it into
        one file per measure on the way in, because that is the layout every analysis
        reads.</div>
      <div class="callout"><b>More than one camera?</b> Some studies film a session
        from several angles. This screen has a collapsed <b>More than one camera per
        session?</b> panel for naming them, and the dashboard grows a camera
        selector. <b>This tutorial doesn't cover it</b> — leave that panel closed if
        each session has one video.</div>
      <p>Press <b>Next →</b>.</p>
    </li>

    <li>
      <h4>Step 3 · Align video &amp; data</h4>
      <p>The dashboard puts your measurements on the video's clock. If a session's
        video and its measurements are not the same length, the dashboard shows dead
        space — video with no data under it, or data running past the end of the
        video.</p>
      <p>This is exactly the kind of problem the example study is here to show you:
        <b>dyad02's video is 12 seconds longer than its measurements</b>. The preview
        shows the video track above each measurement track, so you can see the
        overhang. There are two ways to fix it, and neither touches your original
        files:</p>
      <ul>
        <li><b>Trim the video</b> to a window you pick with the two handles — right if
          the camera was rolling before the session started.</li>
        <li><b>Pad the measurements</b> with zeros at either end — right if the
          measurements genuinely cover a shorter part of the recording.</li>
      </ul>
      <p>For dyad02, trim the video: the camera was rolling before they sat down.
        dyad01 already lines up and needs nothing.</p>
      <figure class="shot" data-shot="04-align.png"
        data-capture="Step 3 showing dyad02: the video track visibly longer than the measurement tracks, with the dual-handle trim slider.">
        <img src="../images/walkthrough/04-align.png"
             alt="Step 3 showing the video track for dyad02 extending past its measurement tracks." />
        <figcaption>The overhang is the 12 seconds. The card's header keeps
          reporting the session as it stands until you press <b>Apply trim</b>;
          dragging the handles previews the window, it does not change anything.
          Trimming writes a trimmed copy at build time — your original video is never
          modified.</figcaption>
      </figure>
      <div class="callout"><b>This step is the only alignment tool DIMS has.</b>
        Build a study <a href="setup.html">from a terminal</a> instead and the files
        have to arrive already lined up — there is no trimming or padding outside the
        builder.</div>
    </li>

    <li>
      <h4>Step 4 · Tabs &amp; analyses</h4>
      <p>Every dashboard shows the video, the measurements and any transcript
        without being asked. This screen is for everything <i>beyond</i> that, and
        all of it is optional — so for now, switch on just two things:</p>
      <ul>
        <li><b>ELAN annotations</b>, so the phases you coded appear on the same
          timeline. It is a switch: nothing to compute, nothing to choose.</li>
        <li><b>Recurrence (RQA)</b>, and pick the single measure
          <code>rtpjSync</code> from the chips underneath it. This is so step 6 has
          something real to do; what recurrence <i>means</i> is further down this
          page, and you can come back for it.</li>
      </ul>
      <p>Leave cross-recurrence, cross-wavelet and the network alone. Each has its
        own section below, and each tells you what it costs before you switch it
        on — cross-wavelet in particular can turn step 6 from a minute into an
        afternoon.</p>
      <figure class="shot" data-shot="05-analyses.png"
        data-capture="Step 4 with only ELAN and recurrence switched on, and rtpjSync the single selected chip under recurrence.">
        <img src="../images/walkthrough/05-analyses.png"
             alt="Step 4 with recurrence switched on and one measure selected." />
        <figcaption>Every analysis has a <b>Settings</b> panel with the tuning a
          study is allowed to change. The defaults are sensible; leave them alone the
          first time.</figcaption>
      </figure>
      <p>Press <b>Next →</b>.</p>
    </li>

    <li>
      <h4>Step 5 · Build</h4>
      <p>Press <b>Build the study</b>. Your files are copied into place, renamed to
        the layout the dashboard expects, and the study's configuration is written and
        checked. It takes a few seconds. Nothing is computed yet.</p>
      <figure class="shot" data-shot="07-build.png"
        data-capture="Step 5 after a successful build: the confirmation and the list of files placed.">
        <img src="../images/walkthrough/07-build.png"
             alt="Step 5 showing a completed build with the list of placed files." />
        <figcaption>Sixteen files placed. If something was wrong, this is where it
          says so, and it names the file.</figcaption>
      </figure>
    </li>

    <li>
      <h4>Step 6 · Compute</h4>
      <p>Press <b>Run the analyses</b>. The builder makes a small Python environment
        just for this study and runs what you switched on, streaming the progress as
        it goes.</p>
      <p>With only recurrence on one measure this is about half a minute — 29 seconds
        measured, most of it building the environment, which happens once. The status line underneath
        counts the seconds, because some analyses go quiet for minutes while they
        work, and a still page is easy to mistake for a stuck one.</p>
      <figure class="shot" data-shot="08-compute.png"
        data-capture="Step 6 mid-run: the live progress log, and the elapsed-time line underneath it.">
        <img src="../images/walkthrough/08-compute.png"
             alt="Step 6 showing live analysis progress streaming into the page." />
        <figcaption>You can leave it. When it finishes, the last step lights up.</figcaption>
      </figure>
    </li>

    <li>
      <h4>Step 7 · Open it</h4>
      <p>Press <b>Open the dashboard</b>. It opens in a new browser tab, running from
        your own machine. That is the whole thing built.</p>
      <p>The same screen gives you copy-and-paste commands to put it online — GitHub
        Pages, Netlify or Vercel — if the data may be published. If you chose
        <b>Private</b> in step 1, publishing is deliberately not a button: it is a
        decision with a checklist.</p>
      <figure class="shot" data-shot="09-open-it.png"
        data-capture="Step 7 with the Open the dashboard button and the deployment commands underneath.">
        <img src="../images/walkthrough/09-open-it.png"
             alt="Step 7 offering to open the dashboard and showing deployment commands." />
        <figcaption>Done.</figcaption>
      </figure>
    </li>
  </ol>
</div>

## What you are looking at

<div class="path builder">
  <p class="sub">The dashboard, and the one gesture the whole tool is built around.</p>
  <p><b>The video, the measurements, the transcript and your ELAN codes share one
    clock.</b> Click anywhere on a measurement trace and the video jumps to that
    moment, with the transcript following along. That's it — that's the tool.</p>
  <figure class="shot" data-shot="10-dashboard-timeseries.png"
    data-capture="The dashboard's main view for dyad01: the traces on the left, video and transcript on the right, playhead parked on the peak at 1:16.">
    <img src="../images/walkthrough/10-dashboard-timeseries.png"
         alt="The DIMS dashboard showing time series, a video panel and a transcript side by side." />
    <figcaption>dyad01 at 1:16, where <code>rtpjSync</code> reaches +0.90. The
      transcript says why: both of them moved here for a job that was supposed to be
      temporary.</figcaption>
  </figure>

  <p>It's worth trying properly, because this is the paper's whole argument in one
    gesture. In dyad01, four peaks are worth clicking: <b>0:49</b> (+0.89),
    <b>1:16</b> (+0.90), <b>2:12</b> (+0.87) and <b>2:33</b> (+0.86). Each is a
    different kind of moment — a joke landing, a mutual disclosure, finishing each
    other's sentence, and a warm aside near the end. In a static plot they'd all
    look the same.</p>
  <p>Then open <b>dyad02</b> and do the same, because this is the half that should
    worry you. Its synchrony sits at zero for most of the conversation, and the one
    moment where these two actually connect is at <b>1:50</b> (+0.70). But its
    highest peaks are somewhere else entirely: <b>2:23</b> (+0.88) on “That's longer
    than it sounds”, <b>1:58</b> (+0.84) on “Exactly”, <b>1:13</b> (+0.81) on “What
    about you?”. Nothing. In a pair who aren't coupled, the biggest peaks land on
    nothing at all — and they're bigger than the one peak that meant something.
    Reading a peak without going back to the recording is how that ends up in a
    paper.</p>

  <p><b>ELAN annotations</b> run along the same timeline as everything else: in the
    example study, the phases of each conversation — warm-up, the topics, the
    shared laughter, the closing.</p>
  <figure class="shot" data-shot="10b-dashboard-elan.png"
    data-capture="The ELAN Annotations tab for dyad01, its phases tier laid along the same timeline as the measurements.">
    <img src="../images/walkthrough/10b-dashboard-elan.png"
         alt="The ELAN annotations tab showing coded conversation phases on the timeline." />
    <figcaption>Your codes, on the clock the rest of the study is on.</figcaption>
  </figure>

  <p class="muted">That is the whole basic dashboard. Everything below is optional:
    four analyses, each in its own section, each saying what it asks of you before
    you switch it on.</p>
</div>

## Going further — the analyses

<p class="lede" style="margin-bottom:18px">Each of these is a switch in step 4 and a
  tab in the dashboard. Switch one on, press <b>Build</b> again, run step 6 again,
  and it appears. They are independent, except where a section says otherwise — and
  they are in the order they make sense to read.</p>

<details class="more">
  <summary><b>Recurrence (RQA)</b>
    <span class="cost">already on · seconds</span>
    <span class="what">Where one signal returns to a state it was in before.</span>
  </summary>
  <div class="more-body">
    <p>You switched this on in step 4, so its tab is already there. A recurrence
      plot asks a single question of a single signal: at which pairs of moments was
      it in nearly the same state? Repeated structure shows up as texture — diagonal
      lines where a stretch of the signal replays a stretch from earlier, blocks
      where it sat still.</p>
    <p>The numbers beside the plot — recurrence rate, determinism, laminarity —
      depend on the <b>target recurrence rate</b> set in step 4's Settings panel. Two
      studies compared with each other must use the same value, or the comparison is
      between two thresholds rather than two conversations.</p>
    <figure class="shot" data-shot="opt-rqa-tab.png"
      data-capture="The recurrence tab for dyad01 rtpjSync — the plot plus the metrics panel beside it.">
      <img src="../images/walkthrough/opt-rqa-tab.png"
           alt="The recurrence tab showing a recurrence plot and its metrics." />
      <figcaption><code>rtpjSync</code> for dyad01. The texture is the point; the
        numbers quantify it.</figcaption>
    </figure>
  </div>
</details>

<details class="more">
  <summary><b>Cross-recurrence (cRQA)</b>
    <span class="cost">adds seconds</span>
    <span class="what">Where two signals repeat <i>each other</i>, and with what delay.</span>
  </summary>
  <div class="more-body">
    <p>Switch on <b>Cross-recurrence (cRQA)</b> in step 4. Every pair is selected by
      default — it is cheap — so click to drop the ones you don't want. For the
      example study, keep <code>personLeftRightHandSpeed × personRightRightHandSpeed</code>:
      two people's right hands.</p>
    <p>The reason that pair is interesting is turn-taking. People take turns, so
      their hands take turns, and a lagged relationship puts the structure
      <i>off</i> the diagonal — the distance from the diagonal is the delay. A
      conversation where one person consistently follows the other looks different
      from one where they overlap.</p>
    <figure class="shot" data-shot="opt-crqa-tab.png"
      data-capture="The Cross-RQA tab for dyad01, the two partners' right hands, with the structure sitting off the diagonal.">
      <img src="../images/walkthrough/opt-crqa-tab.png"
           alt="A cross-recurrence plot for two hand-speed signals." />
      <figcaption>Off-diagonal structure is a lag. On-diagonal would mean they moved
        at the same instant.</figcaption>
    </figure>
  </div>
</details>

<details class="more">
  <summary><b>Cross-wavelet</b>
    <span class="cost">adds ~9 minutes</span>
    <span class="what">Which timescales two signals share, and which one leads.</span>
  </summary>
  <div class="more-body">
    <div class="callout warn"><b>This is the one that costs.</b> On the example
      study — two pairs across two sessions — step 6 goes from <b>29 seconds</b> to
      <b>eight or nine minutes</b> (8:31 and 9:29 on two runs of the same thing).
      Almost all of it is the coherence chance level: a simulation run a hundred
      times for every pair in every session. Without it nothing here can be told from
      coincidence, because two unrelated signals score about 0.25, not 0.</div>
    <p>Switch on <b>Cross-wavelet analysis</b> in step 4 and pick the pairs from the
      chips underneath. Nothing is chosen for you: five measurements make ten
      possible pairs, and each is a separate run. For this study, two is plenty:</p>
    <ul>
      <li><code>personLeftLeftHandSpeed × personRightLeftHandSpeed</code></li>
      <li><code>personLeftRightHandSpeed × personRightRightHandSpeed</code></li>
    </ul>
    <p><code>rtpjSync</code> belongs to the pair rather than to either body, so leave
      it out of the cross-analyses and read it in the time-series tab, where it earns
      its keep.</p>
    <figure class="shot" data-shot="opt-cw-step4.png"
      data-capture="Step 4 with cross-wavelet switched on and two hand pairs selected in its chip row.">
      <img src="../images/walkthrough/opt-cw-step4.png"
           alt="Step 4 showing the cross-wavelet chip row with two pairs selected." />
      <figcaption>Two pairs selected out of ten possible. Each one is a separate run
        of the slowest analysis here.</figcaption>
    </figure>
    <p>In the dashboard, warm regions are shared power and the arrows show the
      lead–lag. The outlined regions are the ones that beat chance.</p>
    <figure class="shot" data-shot="opt-cw-tab.png"
      data-capture="The cross-wavelet tab for dyad01, one of the hand-speed pairs, with the significance contours visible.">
      <img src="../images/walkthrough/opt-cw-tab.png"
           alt="A cross-wavelet coherence plot with significance contours and phase arrows." />
      <figcaption>Warm is shared power; the arrows say who leads; the outlines mark
        what beat chance.</figcaption>
    </figure>
    <div class="callout tip"><b>Two levers, if it's taking too long.</b> The cost is
      pairs × sessions × surrogates. Picking two pairs instead of ten is the first.
      The second is in the cross-wavelet <b>Settings</b> panel: the surrogate count
      is 100, and dropping it to 20 for a first look cuts the step to about a fifth
      (1:42 against 9:29, measured). Put it back to 100 before you draw any
      conclusion from it — a null estimated from 20 samples is a noisy
      threshold.</div>
  </div>
</details>

<details class="more">
  <summary><b>The cross-effector network</b>
    <span class="cost">needs cross-wavelet</span>
    <span class="what">One picture of what is coupled with what, following the playhead.</span>
  </summary>
  <div class="more-body">
    <p><b>Read the cross-wavelet section first.</b> The network's edges come straight
      out of the cross-wavelet analysis — either its coherence or its shared power,
      whichever you pick in the tab — so switching the network on switches
      cross-wavelet on too, and inherits its cost.</p>
    <p>The diagram in step 4 is the one screen that looks unusual. <b>Add a person</b>
      for each figure, <b>click an empty circle</b> on a body to put a measurement
      there, then <b>drag from one placed circle to another</b> to ask for the
      coupling between them — a dashed line follows the pointer. Clicking the two in
      turn does the same thing. Put each partner's two hands on their own figure and
      draw the two lines: four hands, two people, two lines, and that's the whole
      network. Each line is one cross-wavelet pair — the same list as the chips
      above, shown a second way.</p>
    <figure class="shot" data-shot="opt-network-step4.png"
      data-capture="The network diagram with two figures (Left partner, Right partner), each partner's two hands placed on them, and the two lines drawn between them.">
      <img src="../images/walkthrough/opt-network-step4.png"
           alt="The cross-effector network diagram with two human figures and measures on their hands." />
      <figcaption>Two people, their hands, and the lines you want measured.</figcaption>
    </figure>
    <p>In the dashboard the picture moves with the playhead. A thick solid line beats
      the 95 % level in enough of the window to be worth reading; a <b>dashed</b>
      line means the measurement said nothing, which is a result and not a failure.
      Thickness is relative to the other visible lines — the picture answers
      “which of these is strongest here”, and the tooltip gives the number.</p>
    <p><b>Two questions, one picture.</b> <i>Coherence</i> asks whether two measures
      held a steady phase relationship and ignores how much either of them moved;
      <i>shared power</i> asks whether both were moving at that timescale. Read them
      against each other: thick in coherence and thin in power is a coupling computed
      out of stillness, which is the reading to distrust.</p>
    <div class="callout warn"><b>It won't sort your dyads for you.</b> On the example
      study, both dyads come out with a solid line between the partners' <i>left</i>
      hands — 27% of tested cells above chance in dyad01, 27% in dyad02. People take
      turns whether or not the conversation is going anywhere, and their hands take
      turns with them. The one line that separates the two pairs is the right hands:
      solid in dyad01 (28%), dashed in dyad02 (12%). The real difference between
      these two conversations is in <code>rtpjSync</code>, not in the diagram. An
      edge tells you two measures moved together, and coordination isn't rapport.</div>
    <figure class="shot" data-shot="opt-network-tab.png"
      data-capture="The network tab for dyad01 with the playhead on a synchrony peak; if you take a second, dyad02 at the same tab, where the two right hands are joined by a dashed line.">
      <img src="../images/walkthrough/opt-network-tab.png"
           alt="The cross-effector network showing two figures with lines between their measures." />
    </figure>
  </div>
</details>

## When something is not right

<div class="path builder">
  <table class="spec">
    <tr><th>What you see</th><th>What it means</th></tr>
    <tr><td>A file the builder ignored</td>
        <td>Its name does not match anything it recognises. Check the extension and
          that the session ID matches the video's.</td></tr>
    <tr><td>“No cross-wavelet output was found for this recording”</td>
        <td>The network is drawn from cross-wavelet results, so it needs the pairs
          it draws to have been computed. Reopen the study, check the pairs are
          still selected in step 4, and rebuild.</td></tr>
    <tr><td>An empty tab in the dashboard</td>
        <td>The analysis behind it was not switched on for those measures in step 4.
          Reopen the study, switch it on, rebuild.</td></tr>
    <tr><td>Video and data drifting apart</td>
        <td>The <code>Time</code> column is probably in milliseconds, or the video is
          a different take from the one the measurements came from.</td></tr>
    <tr><td>Step 6 taking very long</td>
        <td>Expected on long recordings with many pairs. Fewer cross-wavelet pairs
          is the first lever; fewer surrogates is the second.</td></tr>
    <tr><td>A network with no lines</td>
        <td>Lines come from cross-wavelet pairs. Two measures with no line between
          them on the step 4 diagram are two circles in the dashboard too.</td></tr>
  </table>
</div>
