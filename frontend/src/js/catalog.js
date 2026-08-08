// ═══ GHAWY CATALOG — one source for courses, instructors and tracks ═══
//
// Everything the public site says about a course or an instructor comes from
// this file. Before it existed, the six course cards were written by hand in
// index.html, again (with different fields) in course-details.html, and a
// third time in the /courses shell — changing a duration meant three edits and
// they had already drifted apart.
//
// ── Where the data actually comes from ──
// The backend exposes two UNAUTHENTICATED endpoints, and we use both:
//
//   GET /api/courses          → every published course: title, thumbnail,
//                               total_lessons, course_time, sort_order
//   GET /api/courses/{id}     → the same plus its lessons (title +
//                               duration_minutes), already filtered to
//                               video_status == "ready"
//
// So live numbers — lesson counts, durations, thumbnails — are read from the
// API and are never stale. What the API does NOT have is the marketing layer:
// a stable slug, an English title, which instructor teaches it, and which
// track it belongs to. That lives in COURSES below and is merged onto the API
// response by `courseId`. If the API is unreachable the static values below
// are used as-is, so the page still renders.
//
// ── Curation ──
// COURSES is also the running order of the public site: a course appears on
// the marketing pages because it has an entry here, not because it is
// published in the platform. That is deliberate — publishing a course for
// members should not silently put it on the home page. To add one: add an
// entry with its `courseId` and it shows up everywhere (home, /courses,
// /course-details, /instructors) with no other change.
//
// ── Adding an instructor ──
// Add an entry to INSTRUCTORS and point a course's `instructor` at its slug.
// Nothing else needs to change: the card, the instructor bar, the instructor
// list and the instructor detail page all read from here.
//
// ── Assets ──
// Instructor photos, client logos and intro videos have not been delivered
// yet. Every one of those fields accepts `null`, and the renderers below draw
// a clean placeholder for it. Dropping the real asset in later is a one-line
// change in THIS file — no HTML or CSS is touched.

(function () {
    'use strict';

    const API_BASE = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
        ? 'http://127.0.0.1:8000'
        : '/api';

    // ─── Instructors ────────────────────────────────────────────
    // `clients` is what goes under "اشتغل مع" on the instructor page.
    //
    // These are CATEGORIES of client, not named brands: the client asked for
    // the individual names to come off the site and to be described by the
    // kind of business instead. So `logo` stays null here — there is no logo
    // for a category. The renderer still supports a logo path (it draws the
    // image instead of the text chip) for the day a named brand is added back
    // with permission to show its mark.
    const INSTRUCTORS = {
        'mohamed-salah': {
            slug: 'mohamed-salah',
            name: { ar: 'محمد صلاح', en: 'Mohamed Salah' },
            photo: './imgs/instructors/mohamed.png',
            role: {
                ar: 'مؤسس غاوي ومدرّب AI Automation',
                en: 'Founder of Ghawy — AI Automation instructor'
            },
            // The course card gives the role one short line beside a 38px
            // avatar, and the full `role` above overflows it. This is the
            // client's wording for that line, not a truncation — `role` stays
            // untouched for the wider places (instructor page, course
            // preview, /instructors list). A course card falls back to `role`
            // for any instructor that has no `roleShort`.
            roleShort: {
                ar: 'مؤسس غاوي',
                en: 'Founder of Ghawy'
            },
            yearsExperience: 4,
            clientsCount: 35,
            clients: [
                { name: { ar: 'أكبر الشركات في مصر', en: "Egypt's biggest companies" }, logo: null },
                { name: { ar: 'أكبر الصيدليات في مصر', en: "Egypt's biggest pharmacies" }, logo: null },
            ],
            links: {
                instagram: 'https://www.instagram.com/ghawy.ai/',
                tiktok: 'https://tiktok.com/@ghawy_official',
                facebook: 'https://facebook.com/ghawyofficial',
            },
            introVideo: null,                  // → "coming soon" placeholder
            bio: {
                ar: 'بدأ أونلاين بيزنس وهو عنده 14 سنة، واشتغل في البرمجة والجرافيك والتسويق قبل ما يستقر على الـ AI والأوتوميشن. أسّس غاوي عشان يبني المصدر العربي اللي كان ناقصه هو نفسه وهو بيتعلّم.',
                en: 'Started an online business at 14 and worked through programming, design and marketing before settling on AI and automation. He founded Ghawy to build the Arabic resource he could not find while learning it himself.'
            }
        },

        // ── The two instructors added with the thumbnails and ML courses ──
        //
        // READ THIS BEFORE FILLING ANYTHING IN BELOW.
        //
        // Four things about these two are confirmed: the name the client
        // used for them, the photo they sent, the Instagram link, and the
        // course each one teaches. That is all that is written here.
        //
        // `yearsExperience`, `clientsCount`, `clients` and `bio` are null on
        // purpose. Both Instagram profiles are behind a login wall, so there
        // was no way to read anything true off them, and inventing an
        // experience figure or a client count for a real person is not a
        // placeholder — it is a false claim with their face next to it. The
        // renderers below all skip a fact that is null, so the cards read as
        // deliberately short rather than broken. Ask the client for these
        // four fields and drop them in; nothing else has to change.
        //
        // `role` is derived only from the confirmed course, nothing more.
        //
        // The display name is the handle the client referred to them by
        // ("ofa", "talkhawy"), identical in both languages because guessing
        // an Arabic spelling of someone's name is the same invention problem.
        // Replace with their real names when the client sends them.
        'ofa': {
            slug: 'ofa',
            name: { ar: 'Ofa', en: 'Ofa' },
            photo: './imgs/instructors/ofa.jpg',
            role: {
                ar: 'مدرّب كورس الثامبنيلز بالـ AI',
                en: 'AI Thumbnails instructor'
            },
            roleShort: { ar: 'مدرّب الثامبنيلز', en: 'Thumbnails instructor' },
            yearsExperience: null,
            clientsCount: null,
            clients: [],
            links: {
                instagram: 'https://www.instagram.com/ofapsd/',
            },
            introVideo: null,
            bio: null,
        },
        'talkhawy': {
            slug: 'talkhawy',
            name: { ar: 'Talkhawy', en: 'Talkhawy' },
            photo: './imgs/instructors/talkhawy.jpg',
            role: {
                ar: 'مدرّب كورس الـ Machine Learning',
                en: 'Machine Learning instructor'
            },
            roleShort: { ar: 'مدرّب Machine Learning', en: 'ML instructor' },
            yearsExperience: null,
            clientsCount: null,
            clients: [],
            links: {
                instagram: 'https://www.instagram.com/talkhawy1/',
            },
            introVideo: null,
            bio: null,
        },
    };

    // ─── Track families ─────────────────────────────────────────
    // The platform has TWO kinds of track and the whole point of /tracks is
    // that a first-time visitor can tell them apart and pick one without
    // asking anybody:
    //
    //   deep    — you are here to learn AI ITSELF. Automation, machine
    //             learning, agents. AI becomes the job.
    //   applied — you already have a job (media buyer, editor, designer) and
    //             you want AI inside it. Your field stays the same.
    //
    // Every field below is a row of the comparison table on /tracks, in that
    // order. Adding a row means adding a key here and one line in
    // COMPARE_ROWS — the table renders itself from these two.
    const FAMILIES = {
        'deep': {
            slug: 'deep',
            accent: 'gold',
            icon: 'fa-solid fa-brain',
            name: { ar: 'مسارات التخصص', en: 'Deep tracks' },
            tagline: { ar: 'بتتعلم الـ AI نفسه', en: 'Learn AI itself' },
            oneLine: {
                ar: 'بتدخل جوه الـ AI نفسه — تفهمه، وتبنيه، وتشتغل بيه كتخصص أساسي.',
                en: 'You go inside AI itself — understand it, build with it, and make it your main craft.'
            },
            goal: {
                ar: 'تبقى متخصص في الـ AI نفسه: تبني أنظمة وأوتوميشن وتشتغل بيها كمصدر دخل.',
                en: 'Become a specialist in AI itself: build systems and automations, and earn from them.'
            },
            who: {
                ar: 'أي حد عايز الـ AI يبقى شغله الأساسي — حتى لو مالوش أي خلفية تقنية دلوقتي.',
                en: 'Anyone who wants AI to be their main job — even with zero technical background today.'
            },
            learn: {
                ar: 'الـ AI بيفكر إزاي، إزاي تتكلم معاه صح، إزاي تبني أوتوميشن وأنظمة كاملة، وإزاي تسلّمها لعميل.',
                en: 'How AI thinks, how to talk to it properly, how to build full automations and systems, and how to deliver them to a client.'
            },
            start: {
                ar: 'من الصفر. مسار الأساسيات هو أول خطوة ومش محتاج قبله أي حاجة.',
                en: 'From zero. The Foundations track is step one and needs nothing before it.'
            },
            outcome: {
                ar: 'تقدر تبني نظام AI كامل من الفكرة للتسليم، وتشتغل بيه لنفسك أو لعملاء.',
                en: 'You can build a complete AI system from idea to delivery, and run it for yourself or for clients.'
            },
            example: {
                ar: 'مثال: حد عايز يفتح وكالة أوتوميشن، أو يشتغل في الـ AI كمهنة.',
                en: 'Example: someone opening an automation agency, or working in AI as a profession.'
            },
        },
        'applied': {
            slug: 'applied',
            accent: 'blue',
            icon: 'fa-solid fa-wand-magic-sparkles',
            name: { ar: 'مسارات التطبيق', en: 'Applied tracks' },
            tagline: { ar: 'بتستخدم الـ AI في شغلك', en: 'Use AI inside your own work' },
            oneLine: {
                ar: 'عندك مجال شغل بالفعل، والمسار بيوريك تحطّ الـ AI جواه فتنجز أسرع وأحسن.',
                en: 'You already have a field, and the track shows you how to put AI inside it so you work faster and better.'
            },
            goal: {
                ar: 'تضيف الـ AI لمجالك الحالي عشان تنجز أسرع ونتيجتك تبقى أقوى — من غير ما تغيّر مجالك.',
                en: 'Add AI to the field you already work in so you move faster and deliver better — without changing careers.'
            },
            who: {
                ar: 'حد شغال في مجال محدد: ميديا باير، صانع محتوى، مونتير، ديزاينر، ماركتير.',
                en: 'Someone already working in a specific field: media buyer, creator, editor, designer, marketer.'
            },
            learn: {
                ar: 'الأدوات والخطوات اللي تخص مجالك بالظبط، بشغل عملي على حالات حقيقية من نفس المجال.',
                en: 'The exact tools and steps for your field, worked hands-on on real cases from that same field.'
            },
            start: {
                ar: 'محتاج تكون فاهم مجالك بس. مش لازم أي خلفية تقنية عن الـ AI.',
                en: 'You only need to know your own field. No technical AI background required.'
            },
            outcome: {
                ar: 'تعمل نفس شغلك في وقت أقل وبجودة أعلى، وتفرق عن اللي حواليك في نفس المجال.',
                en: 'You do the same work in less time and at higher quality, and stand out among your peers.'
            },
            example: {
                ar: 'مثال: ميديا باير عايز كرييتيفز أسرع، أو صانع محتوى عايز ثامبنيلز أقوى.',
                en: 'Example: a media buyer who wants creatives faster, or a creator who wants stronger thumbnails.'
            },
        },
    };

    // The comparison table on /tracks: one row per key, both families side by
    // side. The question each row answers is the row label — they are written
    // as the questions a visitor actually has, not as feature names.
    const COMPARE_ROWS = [
        { key: 'goal', icon: 'fa-solid fa-bullseye', label: { ar: 'الهدف منه إيه؟', en: 'What is it for?' } },
        { key: 'who', icon: 'fa-solid fa-user-check', label: { ar: 'مناسب لمين؟', en: 'Who is it for?' } },
        { key: 'learn', icon: 'fa-solid fa-book-open', label: { ar: 'هتتعلم فيه إيه؟', en: 'What will you learn?' } },
        { key: 'start', icon: 'fa-solid fa-flag-checkered', label: { ar: 'تبدأ منين؟', en: 'Where do you start?' } },
        { key: 'outcome', icon: 'fa-solid fa-trophy', label: { ar: 'هتطلع منه بإيه؟', en: 'What do you walk out with?' } },
    ];

    // ─── Tracks ─────────────────────────────────────────────────
    // A track belongs to exactly one family and holds NO course list: which
    // courses are in it is derived by filtering COURSES on `track`, so the
    // relation is written once (on the course) and can never disagree with
    // itself. `coursesInTrack()` below is the only way to read it.
    //
    // `image: null` renders the themed placeholder — see trackThumbHTML().
    // Dropping the real artwork in later is one path per track in THIS file;
    // no HTML and no CSS changes.
    //
    // ── How the courses were assigned ──
    // The client's words were: Foundations = "AI Foundations only", and
    // Automation = "from AAA Core to Practical AI Systems". The platform
    // numbers its own courses 1..6 in the order they are meant to be taken
    // (see GET /api/courses → sort_order), and that numbering is:
    //
    //   1- AI Foundations   2- AAA Core   3- Prompt Engineering
    //   4- AI Automation Lab   5- Practical AI Systems   6- Client Acquisition
    //
    // So "from AAA Core to Practical AI Systems" is the contiguous run 2→5,
    // which puts Prompt Engineering (3) inside the automation track. Client
    // Acquisition (6) falls outside that run; it closes the same agency
    // journey — build the system, then go sell it — so it sits at the end of
    // the automation track rather than in a family about using AI in another
    // field. Both placements are flagged for the client to confirm.
    const TRACKS = {
        'foundations': {
            slug: 'foundations',
            family: 'deep',
            icon: 'fa-solid fa-cube',
            image: null,
            name: { ar: 'الأساسيات', en: 'Foundations' },
            short: { ar: 'نقطة البداية لأي حد', en: 'The starting point for everyone' },
            about: {
                ar: 'أول خطوة على المنصة. تفهم الـ AI بيشتغل إزاي بالظبط، إيه اللي يقدر يعمله وإيه اللي مايقدرش، وتستخدمه في يومك — قبل ما تتخصص في أي حاجة.',
                en: 'The first step on the platform. You learn how AI actually works, what it can and cannot do, and how to use it day to day — before you specialise in anything.'
            },
            forWho: {
                ar: 'لو مالكش أي خلفية عن الـ AI، ابدأ من هنا. المسار ده مفروض قبل أي مسار تاني.',
                en: 'If you have no AI background at all, start here. This track comes before every other one.'
            },
            startsFrom: {
                ar: 'من الصفر — مش محتاج أي حاجة قبله.',
                en: 'From zero — nothing is required before it.'
            },
            outcomes: [
                { ar: 'تفهم الـ AI بيشتغل إزاي وإيه حدوده، وتبطّل تخمين', en: 'Understand how AI works and where its limits are — no more guessing' },
                { ar: 'تعرف تختار الأداة الصح لكل مهمة بدل ما تجرّب عشوائي', en: 'Pick the right tool for each task instead of trying at random' },
                { ar: 'تستخدم الـ AI في شغلك اليومي من أول أسبوع', en: 'Use AI in your day-to-day work from the first week' },
                { ar: 'تبقى جاهز تدخل أي مسار تخصص من غير ما تتوه', en: 'Be ready to enter any specialisation track without getting lost' },
            ],
        },
        'automation': {
            slug: 'automation',
            family: 'deep',
            icon: 'fa-solid fa-diagram-project',
            image: null,
            name: { ar: 'الأوتوميشن', en: 'AI Automation' },
            short: { ar: 'تبني أنظمة بتشتغل لوحدها', en: 'Build systems that run themselves' },
            about: {
                ar: 'المسار الأساسي في غاوي. تتعلم تبني أنظمة بالـ AI بتشتغل لوحدها من غير ما تقف عليها — من أول فكرة النظام، لبنائه، لتشغيله لعميل حقيقي وتحصيل فلوسك منه.',
                en: 'The main track at Ghawy. You learn to build AI systems that run without you standing over them — from the idea, to building it, to running it for a real client and getting paid.'
            },
            forWho: {
                ar: 'اللي عايز يشتغل في الـ AI كمهنة أو يفتح وكالة أوتوميشن خاصة بيه.',
                en: 'For anyone who wants AI as a profession, or to open their own automation agency.'
            },
            startsFrom: {
                ar: 'يفضّل تخلّص مسار الأساسيات الأول — بس مش شرط لو عندك خلفية.',
                en: 'Finish the Foundations track first if you can — not mandatory if you already have a background.'
            },
            outcomes: [
                { ar: 'تبني أوتوميشن كامل بيشتغل لوحده من غير متابعة يومية', en: 'Build a complete automation that runs on its own with no daily babysitting' },
                { ar: 'تحوّل شغل يدوي بياخد ساعات لنظام بيخلّص في دقايق', en: 'Turn manual work that takes hours into a system that finishes in minutes' },
                { ar: 'تتكلم مع الـ AI بطريقة تجيب النتيجة اللي في دماغك بالظبط', en: 'Talk to AI in a way that returns exactly the result you had in mind' },
                { ar: 'تسعّر النظام وتسلّمه لعميل زي المحترفين', en: 'Price the system and hand it over to a client like a professional' },
                { ar: 'تلاقي عملاء وتقفل معاهم صفقات على شغل الأوتوميشن', en: 'Find clients and close deals on automation work' },
            ],
        },
        'machine-learning': {
            slug: 'machine-learning',
            family: 'deep',
            icon: 'fa-solid fa-microchip',
            image: null,
            name: { ar: 'Machine Learning', en: 'Machine Learning' },
            short: { ar: 'تبني الموديل بنفسك', en: 'Build the model yourself' },
            about: {
                ar: 'الطريق العميق. بدل ما تستخدم موديل جاهز، تفهم الموديلات بتتعلّم إزاي من جوه وتبني واحد بنفسك وتقيس دقته.',
                en: 'The deep road. Instead of using a ready-made model, you understand how models learn from the inside, build one yourself, and measure how good it is.'
            },
            forWho: {
                ar: 'اللي عايز يروح لآخر مدى في الـ AI ويشتغل على الداتا والموديلات نفسها.',
                en: 'For anyone who wants to go all the way into AI and work on the data and the models themselves.'
            },
            startsFrom: {
                ar: 'بعد الأساسيات. المسار ده أعمق من اللي قبله.',
                en: 'After Foundations. This track goes deeper than the ones before it.'
            },
            outcomes: [
                { ar: 'تفهم الموديلات بتتدرّب إزاي من جوه', en: 'Understand how models are trained from the inside' },
                { ar: 'تبني موديل بنفسك وتقيس دقته', en: 'Build a model yourself and measure its accuracy' },
                { ar: 'تشتغل على الداتا بدل ما تستنى أدوات جاهزة', en: 'Work on the data instead of waiting for ready-made tools' },
            ],
        },
        'ai-thumbnails': {
            slug: 'ai-thumbnails',
            family: 'applied',
            icon: 'fa-solid fa-image',
            image: null,
            name: { ar: 'AI للثامبنيلز', en: 'AI for Thumbnails' },
            short: { ar: 'ثامبنيل يوقف السكرول', en: 'Thumbnails that stop the scroll' },
            about: {
                ar: 'تعمل ثامبنيلز بالـ AI توقف السكرول وترفع نسبة الضغط على الفيديو — من غير ما تكون ديزاينر ومن غير ما تستنى حد يعملهالك.',
                en: 'Make thumbnails with AI that stop the scroll and lift your click-through — without being a designer and without waiting on anyone.'
            },
            forWho: {
                ar: 'صنّاع المحتوى والمونتيرين واللي شغالين على قنوات يوتيوب.',
                en: 'Creators, editors, and anyone running a YouTube channel.'
            },
            startsFrom: {
                ar: 'من غير أي خلفية عن الـ AI ولا عن الديزاين.',
                en: 'With no AI and no design background.'
            },
            outcomes: [
                { ar: 'تطلّع أفكار ثامبنيل بالـ AI في دقايق', en: 'Generate thumbnail concepts with AI in minutes' },
                { ar: 'تنفّذ الثامبنيل بنفسك من غير خبرة ديزاين', en: 'Execute the thumbnail yourself with no design experience' },
                { ar: 'تختبر أكتر من نسخة وتعرف أنهي واحدة بتشتغل', en: 'Test several versions and know which one actually works' },
            ],
        },
        'ai-media-buying': {
            slug: 'ai-media-buying',
            family: 'applied',
            icon: 'fa-solid fa-bullhorn',
            image: null,
            name: { ar: 'AI للميديا باينج', en: 'AI for Media Buying' },
            short: { ar: 'حملات أسرع وقرارات أدق', en: 'Faster campaigns, sharper calls' },
            about: {
                ar: 'تستخدم الـ AI في الإعلانات: كرييتيفز ونسخ إعلانية بأعداد كبيرة، وقراءة أرقام الحملة بسرعة عشان تاخد قرارك وانت شايف.',
                en: 'Use AI across your ads: creatives and ad copy at volume, and fast reading of campaign numbers so you decide with your eyes open.'
            },
            forWho: {
                ar: 'الميديا باينج والبيرفورمانس ماركتينج واللي بيديروا حملات إعلانية.',
                en: 'Media buyers, performance marketers, and anyone running paid campaigns.'
            },
            startsFrom: {
                ar: 'محتاج تكون شغال في الإعلانات بالفعل — مش محتاج خلفية تقنية.',
                en: 'You need to already work in ads — no technical background required.'
            },
            outcomes: [
                { ar: 'تعمل كرييتيفز إعلانية بالـ AI بسرعة وبأعداد', en: 'Produce ad creatives with AI quickly and at volume' },
                { ar: 'تكتب نسخ إعلانية متعددة وتختبرها', en: 'Write multiple ad copy variants and test them' },
                { ar: 'تقرأ أرقام الحملة وتاخد قرار أسرع', en: 'Read campaign numbers and decide faster' },
            ],
        },
    };

    // ─── Courses ────────────────────────────────────────────────
    // `courseId` is the row id in the platform database — the join key for the
    // API merge. `lessons`/`duration` here are only the offline fallback; the
    // API overwrites them when it answers.
    //
    // THE ORDER OF THIS ARRAY IS THE ORDER OF THE SITE. It is the card order
    // on the home page and on /courses, and — because a track's course list is
    // just this array filtered — it is also the step order inside a track. It
    // matches the platform's own numbering (the "1-", "2-" … prefixes on the
    // course titles, i.e. sort_order from GET /api/courses), which is the order
    // the courses are meant to be taken in.
    //
    // `track` is the ONLY place the course↔track relation is written; the
    // tracks themselves hold no course list. See the note above TRACKS for why
    // each course landed where it did.
    const COURSES = [
        {
            slug: 'ai-foundations',
            courseId: 5,
            title: { ar: 'أساسيات الذكاء الاصطناعي', en: 'AI Foundations' },
            image: './imgs/course1.jpg',
            lessons: 10,
            duration: '12h 3m',
            track: 'foundations',
            instructor: 'mohamed-salah',
        },
        {
            slug: 'aaa-core',
            courseId: 6,
            title: { ar: 'بيزنس وكالة الاوتوميشن', en: 'AAA Core' },
            image: './imgs/course2.jpg',
            lessons: 7,
            duration: '12h 11m',
            track: 'automation',
            instructor: 'mohamed-salah',
        },
        {
            slug: 'prompt-engineering',
            courseId: 7,
            title: { ar: 'هندسة البرومبت', en: 'Prompt Engineering' },
            image: './imgs/course3.jpg',
            lessons: 4,
            duration: '5h 3m',
            track: 'automation',
            instructor: 'mohamed-salah',
        },
        {
            slug: 'ai-automation-lab',
            courseId: 8,
            title: { ar: 'اوتوميشن الذكاء الاصطناعي', en: 'AI Automation Lab' },
            image: './imgs/course4.jpg',
            lessons: 11,
            duration: '9h 36m',
            track: 'automation',
            instructor: 'mohamed-salah',
        },
        {
            slug: 'practical-ai-systems',
            courseId: 10,
            title: { ar: 'مشاريع AI عملية', en: 'Practical AI Systems' },
            image: './imgs/course5.jpg',
            lessons: 3,
            duration: '4h 7m',
            track: 'automation',
            instructor: 'mohamed-salah',
        },
        {
            slug: 'client-acquisition',
            courseId: 9,
            title: { ar: 'اكتساب العملاء', en: 'Client Acquisition' },
            image: './imgs/course6.jpg',
            lessons: 6,
            duration: '7h 47m',
            track: 'automation',
            instructor: 'mohamed-salah',
        },
        // Published in the platform since July but never listed here, so the
        // public site did not know it existed. Numbers, thumbnail and lesson
        // list all came from the platform (course id 12).
        //
        // Track: `automation`. The lessons are CLAUDE.md, context management,
        // MCPs, Skills, Agents and "Use Cases & Build" — that is building
        // systems that run themselves, which is what the automation track
        // says it teaches. It is not Foundations (that track is "no
        // background required" and this one assumes you already work with
        // AI). The client has not confirmed the placement — see the note on
        // prompt-engineering and client-acquisition.
        {
            slug: 'claude-code',
            courseId: 12,
            title: { ar: 'كلود كود', en: 'Claude Code' },
            image: './imgs/course7.jpg',
            lessons: 7,
            duration: '5h 56m',
            track: 'automation',
            instructor: 'mohamed-salah',
        },

        // ── Announced, not released ──
        //
        // These two are deliberately missing `courseId`, `lessons` and
        // `duration`, and that absence IS the state: `isSoon()` below treats a
        // course with no runtime as not-yet-available, and every place that
        // shows a runtime, a course count or a total reads that flag instead
        // of guessing from a zero. So the cards say "قريباً" where the hours
        // would go, the "محتوى الكورس" button is inert, and the two tracks
        // they belong to keep reading "coming soon" rather than suddenly
        // claiming "1 course · 0 hours".
        //
        // Releasing one is a three-line change here and nothing else: give it
        // the platform's `courseId` and its static `lessons`/`duration`
        // fallback. `load()` will then merge the live numbers over the top and
        // the course flips to available everywhere on the site at once.
        //
        // No `image` yet either — `courseMediaHTML` draws the track's icon on
        // its family gradient until the client sends the thumbnails.
        {
            slug: 'ai-thumbnails',
            title: { ar: 'الثامبنيلز بالذكاء الاصطناعي', en: 'AI Thumbnails' },
            image: null,
            track: 'ai-thumbnails',
            instructor: 'ofa',
        },
        {
            slug: 'machine-learning',
            title: { ar: 'Machine Learning', en: 'Machine Learning' },
            image: null,
            track: 'machine-learning',
            instructor: 'talkhawy',
        },
    ];

    // ─── Helpers ────────────────────────────────────────────────

    function lang() {
        return (typeof window.currentLang === 'function') ? window.currentLang() : 'ar';
    }

    /**
     * Pick the current language out of an {ar, en} pair.
     *
     * The fallback fires on a MISSING side only, never on an empty one: a pair
     * may deliberately be empty in one language — the course preview says
     * "ضمن مسار <name>" in Arabic but "Part of the <name> track" in English,
     * so the trailing word is `{ ar: '', en: 'track' }`. Falling back on ''
     * would have printed the English word inside the Arabic sentence.
     */
    function L(pair) {
        if (pair == null) return '';
        if (typeof pair === 'string') return pair;
        const v = pair[lang()];
        if (v != null) return v;
        return pair.ar != null ? pair.ar : (pair.en != null ? pair.en : '');
    }

    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        })[c]);
    }

    /** Both-language attributes, so i18n.js can translate rendered markup. */
    function i18nAttrs(pair) {
        if (pair == null) return '';
        if (typeof pair === 'string') return `data-ar="${esc(pair)}" data-en="${esc(pair)}"`;
        return `data-ar="${esc(pair.ar || '')}" data-en="${esc(pair.en || pair.ar || '')}"`;
    }

    /** Media paths from the API are server-relative; the images live behind /api. */
    function mediaURL(url) {
        if (!url) return null;
        return url.startsWith('/') ? API_BASE + url : url;
    }

    /**
     * Is this course announced but not out yet?
     *
     * A released course always has a runtime — the platform gives it one the
     * moment a lesson is ready, and the static fallback in COURSES carries one
     * too. So "no runtime" is the single, self-maintaining signal that a
     * course is not watchable yet, and it needs no extra flag to be kept in
     * sync by hand: the day the API returns a `course_time` for one of these,
     * it stops being "soon" everywhere at once.
     */
    function isSoon(course) {
        return !course || !course.duration;
    }

    /** "12h 11m" → 731 minutes. Returns 0 for anything unparseable. */
    function durationToMinutes(text) {
        if (!text) return 0;
        const h = /(\d+)\s*h/i.exec(text);
        const m = /(\d+)\s*m/i.exec(text);
        return (h ? parseInt(h[1], 10) * 60 : 0) + (m ? parseInt(m[1], 10) : 0);
    }

    function minutesToDuration(mins) {
        const h = Math.floor(mins / 60);
        const m = Math.round(mins % 60);
        return h ? (m ? `${h}h ${m}m` : `${h}h`) : `${m}m`;
    }

    function instructor(slug) {
        return INSTRUCTORS[slug] || null;
    }

    function track(slug) {
        return TRACKS[slug] || null;
    }

    function family(slug) {
        return FAMILIES[slug] || null;
    }

    /** The two families in display order — deep first, it is the main road. */
    function familyList() {
        return ['deep', 'applied'].map(k => FAMILIES[k]);
    }

    /** The tracks of one family, in declaration order. */
    function trackList(familySlug) {
        return Object.keys(TRACKS)
            .map(k => TRACKS[k])
            .filter(t => !familySlug || t.family === familySlug);
    }

    /** Where a track lives on the site. One place builds this URL. */
    function trackHref(slug) {
        return `/tracks?t=${encodeURIComponent(slug)}`;
    }

    // ─── Loading + merging ──────────────────────────────────────

    let loadPromise = null;

    /**
     * The catalog, with live numbers merged in from GET /api/courses.
     * Resolves with the static catalog if the request fails — the site must
     * never render an empty course list because the API blinked. Cached: every
     * consumer on a page shares one request.
     */
    function load() {
        if (loadPromise) return loadPromise;

        const fallback = COURSES.map(c => Object.assign({}, c, { live: false }));

        loadPromise = fetch(`${API_BASE}/courses`, { headers: { 'Accept': 'application/json' } })
            .then(r => r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status)))
            .then(rows => {
                const byId = new Map(rows.map(r => [r.id, r]));
                return COURSES.map(c => {
                    const row = byId.get(c.courseId);
                    if (!row) return Object.assign({}, c, { live: false });
                    return Object.assign({}, c, {
                        live: true,
                        lessons: row.total_lessons || c.lessons,
                        duration: row.course_time || c.duration,
                        image: mediaURL(row.thumbnail_url) || c.image,
                    });
                });
            })
            .catch(err => {
                console.warn('[catalog] falling back to static course data:', err.message);
                return fallback;
            });

        return loadPromise;
    }

    /** One course with its live numbers, or null for an unknown slug. */
    function courseBySlug(slug) {
        return load().then(list => list.find(c => c.slug === slug) || null);
    }

    /** The lessons of one course, straight from the public detail endpoint. */
    function lessonsFor(course) {
        if (!course || !course.courseId) return Promise.resolve([]);
        return fetch(`${API_BASE}/courses/${course.courseId}`, { headers: { 'Accept': 'application/json' } })
            .then(r => r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status)))
            .then(d => (d.lessons || []).map(l => ({
                title: l.title,
                duration: minutesToDuration(l.duration_minutes || 0),
            })))
            .catch(err => {
                console.warn('[catalog] lessons unavailable:', err.message);
                return [];
            });
    }

    /** Every course taught by one instructor, in catalog order. */
    function coursesByInstructor(slug) {
        return load().then(list => list.filter(c => c.instructor === slug));
    }

    /**
     * The courses of one track, in the order they are meant to be taken.
     * This is the ONLY reader of the course↔track relation: tracks carry no
     * course list of their own, so the two can never drift apart. The order is
     * COURSES order, which is the platform's own course numbering.
     */
    function coursesInTrack(slug) {
        return load().then(list => list.filter(c => c.track === slug));
    }

    /**
     * Counts for one track, with its course list.
     *
     * There are THREE states here, not two, and conflating the last two is
     * what would have gone wrong the moment a course was announced without a
     * date:
     *
     *   empty   — nothing announced at all.
     *   soon    — something announced, none of it watchable yet.
     *   normal  — at least one course you can open today.
     *
     * `empty` used to be the only flag, so a track flipped straight from
     * "قريباً" to "1 course · 0 hours" as soon as an unreleased course was
     * added to it — louder AND less true than the state it replaced. Both of
     * the first two states render as "coming soon"; `count`/`hours` describe
     * only what is actually watchable, and `soonCount` carries the rest.
     */
    function trackStats(slug) {
        return coursesInTrack(slug).then(courses => {
            const t = totals(courses);
            return {
                courses: courses,
                empty: courses.length === 0,
                // Announced but nothing to watch — reads as "coming soon" too.
                soon: courses.length > 0 && t.courses === 0,
                soonCount: t.soon,
                count: t.courses,
                announced: t.announced,
                lessons: t.lessons,
                hours: t.hours,
                minutes: t.minutes,
                instructors: Array.from(new Set(courses.map(c => c.instructor)))
                    .map(instructor).filter(Boolean),
            };
        });
    }

    /** Every track with its counts already resolved — for the list views. */
    function trackListWithStats(familySlug) {
        const tracks = trackList(familySlug);
        return Promise.all(tracks.map(t =>
            trackStats(t.slug).then(stats => ({ track: t, stats }))
        ));
    }

    /** Instructors in a stable order, so the list page never reshuffles. */
    function instructorList() {
        return Object.keys(INSTRUCTORS).map(k => INSTRUCTORS[k]);
    }

    /**
     * Totals across the whole catalog — for the "all of Ghawy" bar.
     *
     * `courses`, `lessons`, `minutes` and `hours` count ONLY courses that are
     * actually watchable. An announced-but-unreleased course would otherwise
     * push the headline course count up while adding nothing to the hours,
     * which is the site promising more than a subscriber can open — the
     * numbers on this site are a claim about what you get for your money, and
     * a course with no lessons in it is not part of that.
     *
     * `announced` and `soon` are kept alongside for the places that DO want to
     * say "and two more are on the way".
     */
    function totals(list) {
        const all = list || COURSES;
        const out = all.filter(c => !isSoon(c));
        const mins = out.reduce((s, c) => s + durationToMinutes(c.duration), 0);
        return {
            courses: out.length,
            lessons: out.reduce((s, c) => s + (c.lessons || 0), 0),
            minutes: mins,
            hours: Math.round(mins / 60),
            announced: all.length,
            soon: all.length - out.length,
        };
    }

    // ─── Renderers ──────────────────────────────────────────────

    /** Initials for the avatar placeholder, e.g. "محمد صلاح" → "م ص". */
    function initials(name) {
        return String(name || '?').trim().split(/\s+/).slice(0, 2)
            .map(w => w[0]).join(' ');
    }

    function avatarHTML(inst, cls) {
        const name = L(inst.name);
        if (inst.photo) {
            return `<img class="${cls}" src="${esc(inst.photo)}" alt="${esc(name)}" loading="lazy" />`;
        }
        // Placeholder: initials on the brand gradient. Replaced the moment
        // `photo` gets a path in this file.
        return `<span class="${cls} gi-avatar-fallback" aria-hidden="true">${esc(initials(name))}</span>`;
    }

    /**
     * The instructor bar: photo + name + role, linking to their page. Used
     * under the course preview and on the track pages. The course card no
     * longer uses it — its reference wants the instructor flat on one edge of
     * a row, not in a pill with a role line, so it has `cardInstructorHTML`.
     *
     * There used to be a second `full` variant that boxed the identity, the
     * facts, the client strip and the intro video into one card. It was
     * dropped — the box left a lot of dead space around the video and read
     * badly. The instructor page now lays those parts out flat down the page
     * instead, using the individual renderers below.
     */
    function instructorBarHTML(inst) {
        if (!inst) return '';
        return `
        <a class="gi-bar gi-bar-compact" href="/instructors?i=${encodeURIComponent(inst.slug)}">
            ${avatarHTML(inst, 'gi-avatar')}
            <span class="gi-ident">
                <span class="gi-name">${esc(L(inst.name))}</span>
                <span class="gi-role" ${i18nAttrs(inst.role)}>${esc(L(inst.role))}</span>
            </span>
        </a>`;
    }

    /**
     * "خبرة أكتر من N سنين", or null when we do not know N.
     *
     * Every caller used to build this line unconditionally, which printed
     * "خبرة أكتر من undefined سنين" for an instructor whose figures the client
     * has not sent yet. A fact we do not have is not rendered at all.
     */
    function yearsLineFor(inst) {
        if (!inst || !inst.yearsExperience) return null;
        return {
            ar: `خبرة أكتر من ${inst.yearsExperience} سنين`,
            en: `${inst.yearsExperience}+ years of experience`,
        };
    }

    /** The experience / client-count pills. Omitted entirely if we have neither. */
    function factsHTML(inst) {
        const yearsLine = yearsLineFor(inst);
        const clientsLine = inst.clientsCount ? {
            ar: `اشتغل مع أكتر من ${inst.clientsCount} عميل`,
            en: `Worked with ${inst.clientsCount}+ clients`,
        } : null;
        if (!yearsLine && !clientsLine) return '';
        return `
        <div class="gi-facts">
            ${yearsLine ? `<span class="gi-fact" ${i18nAttrs(yearsLine)}>${esc(L(yearsLine))}</span>` : ''}
            ${clientsLine ? `<span class="gi-fact" ${i18nAttrs(clientsLine)}>${esc(L(clientsLine))}</span>` : ''}
        </div>`;
    }

    /** The brands/creators strip. Chips today, images the moment a logo is set. */
    function clientsHTML(inst) {
        const chips = (inst.clients || []).map(c => c.logo
            ? `<span class="gi-client"><img src="${esc(c.logo)}" alt="${esc(L(c.name))}" loading="lazy" /></span>`
            : `<span class="gi-client gi-client-text" ${i18nAttrs(c.name)}>${esc(L(c.name))}</span>`
        ).join('');
        return chips ? `<div class="gi-clients-row">${chips}</div>` : '';
    }

    /**
     * The course's own intro video for the preview page. Autoplays — which
     * browsers only allow while muted, so `muted` is not optional here — and
     * loops, because it is a short teaser rather than a lesson.
     * `introVideo: null` (all of them, today) renders the placeholder instead.
     */
    function courseVideoHTML(course) {
        if (course && course.introVideo) {
            return `
        <div class="cd-video">
            <video src="${esc(course.introVideo)}" poster="${esc(course.image || '')}"
                   autoplay muted loop playsinline controls></video>
        </div>`;
        }
        return `
        <div class="cd-video cd-video-empty">
            ${course && course.image ? `<img src="${esc(course.image)}" alt="" loading="lazy" />` : ''}
            <div class="cd-video-empty-body">
                <i class="fa-solid fa-circle-play" aria-hidden="true"></i>
                <span data-ar="فيديو مقدمة الكورس قريباً" data-en="Course intro video coming soon">فيديو مقدمة الكورس قريباً</span>
            </div>
        </div>`;
    }

    /** The 2-minute intro video, or a labelled placeholder until it arrives. */
    function introVideoHTML(inst) {
        if (inst.introVideo) {
            return `
        <div class="gi-video">
            <video src="${esc(inst.introVideo)}" controls playsinline preload="none"
                   poster="${esc(inst.introVideoPoster || '')}"></video>
        </div>`;
        }
        return `
        <div class="gi-video gi-video-empty">
            <i class="fa-solid fa-circle-play" aria-hidden="true"></i>
            <span data-ar="الفيديو التعريفي للمدرّب قريباً" data-en="Instructor intro video coming soon">الفيديو التعريفي للمدرّب قريباً</span>
        </div>`;
    }

    /**
     * Social links. Only the platforms actually present on the instructor are
     * rendered, so adding one is a single key in INSTRUCTORS.
     */
    const LINK_ICONS = {
        instagram: 'fa-brands fa-instagram',
        tiktok: 'fa-brands fa-tiktok',
        facebook: 'fa-brands fa-facebook-f',
        youtube: 'fa-brands fa-youtube',
        linkedin: 'fa-brands fa-linkedin-in',
        x: 'fa-brands fa-x-twitter',
        website: 'fa-solid fa-globe',
    };

    function linksHTML(inst) {
        const links = inst.links || {};
        const items = Object.keys(links)
            .filter(k => links[k] && LINK_ICONS[k])
            .map(k => `
            <a class="gi-link" href="${esc(links[k])}" target="_blank" rel="noopener noreferrer"
               aria-label="${esc(k)}"><i class="${LINK_ICONS[k]}" aria-hidden="true"></i></a>`)
            .join('');
        return items ? `<div class="gi-links">${items}</div>` : '';
    }

    /** One instructor card for the /instructors list. */
    function instructorCardHTML(inst) {
        const href = `/instructors?i=${encodeURIComponent(inst.slug)}`;
        const name = L(inst.name);
        // Null for an instructor whose figures we have not been given — the
        // pill is dropped rather than printed with an "undefined" in it.
        const years = yearsLineFor(inst);
        return `
    <article class="gi-card">
        <a class="gi-card-top" href="${href}">
            ${avatarHTML(inst, 'gi-avatar gi-avatar-lg')}
            <span class="gi-ident">
                <span class="gi-name gi-name-lg">${esc(name)}</span>
                <span class="gi-role" ${i18nAttrs(inst.role)}>${esc(L(inst.role))}</span>
            </span>
        </a>
        ${years ? `<span class="gi-fact" ${i18nAttrs(years)}>${esc(L(years))}</span>` : ''}
        <a class="gc-btn" href="${href}" data-ar="صفحة المدرّب" data-en="Instructor page">صفحة المدرّب</a>
    </article>`;
    }

    /**
     * How many courses this instructor teaches on Ghawy.
     *
     * Counted off COURSES rather than `coursesByInstructor`, which is the
     * async one. Both give the same number — `load()` maps over COURSES and
     * only ever refreshes the lesson count, runtime and thumbnail of an entry,
     * so the API can never add or remove a course from the list — and counting
     * here keeps the instructor card synchronous, which means no skeleton and
     * no number that changes under the reader a second after it appears.
     */
    function courseCountFor(slug) {
        return COURSES.filter(c => c.instructor === slug && !isSoon(c)).length;
    }

    /** Announced-but-unreleased courses for one instructor. */
    function soonCountFor(slug) {
        return COURSES.filter(c => c.instructor === slug && isSoon(c)).length;
    }

    /**
     * The instructor card on the home page.
     *
     * The client's ask was "say what this instructor is distinguished at", and
     * everything that answers it is already in INSTRUCTORS: the role, the
     * years, the kinds of client they have worked with. So the card composes
     * that one line out of those fields instead of asking for a new one —
     * adding a second instructor stays a single entry in this file.
     *
     * Different card from `instructorCardHTML`: /instructors is a directory
     * and its card is deliberately sparse, while this one is doing the
     * persuading on a landing page and carries the course count, the
     * distinction line and the social links.
     */
    function homeInstructorCardHTML(inst) {
        const href = `/instructors?i=${encodeURIComponent(inst.slug)}`;
        // Courses out today, and courses announced. An instructor whose only
        // course has not shipped yet gets "كورس واحد قريباً" — saying "كورس
        // واحد على غاوي" would point at something nobody can open.
        const n = courseCountFor(inst.slug);
        const soonN = soonCountFor(inst.slug);
        const courses = n
            ? { ar: `${L(coursesWord(n))} على غاوي`, en: `${L(coursesWord(n))} on Ghawy` }
            : soonN
                ? { ar: `${coursesWord(soonN).ar} قريباً`, en: `${coursesWord(soonN).en} coming soon` }
                : null;

        const years = yearsLineFor(inst);

        // What he is known for. The role is already the line under his name,
        // so this one picks up where that leaves off: who he has actually done
        // it for. `clients` holds CATEGORIES of client, so it reads as a
        // description and never as a name-drop. With no clients on file it
        // falls back to the bio; with no bio either — an instructor whose
        // details the client has not sent yet — the line is left out rather
        // than rendered as an empty paragraph.
        const clientNames = (inst.clients || []).map(c => c.name);
        const distinction = clientNames.length ? {
            ar: `اشتغل مع ${clientNames.map(c => c.ar).join(' و')}، وبيشرح على غاوي اللي بيعمله فعلاً في شغله.`,
            en: `Has worked with ${clientNames.map(c => c.en || c.ar).join(' and ')}, and teaches on Ghawy exactly what he does in that work.`,
        } : inst.bio;

        const facts = [
            courses ? `
            <span class="hi-fact">
                <i class="fa-solid fa-graduation-cap" aria-hidden="true"></i>
                <span ${i18nAttrs(courses)}>${esc(L(courses))}</span>
            </span>` : '',
            years ? `
            <span class="hi-fact">
                <i class="fa-solid fa-briefcase" aria-hidden="true"></i>
                <span ${i18nAttrs(years)}>${esc(L(years))}</span>
            </span>` : '',
        ].join('');

        return `
    <article class="hi-card">
        <a class="hi-top" href="${href}">
            ${avatarHTML(inst, 'hi-avatar')}
            <span class="hi-ident">
                <span class="hi-name">${esc(L(inst.name))}</span>
                <span class="hi-role" ${i18nAttrs(inst.role)}>${esc(L(inst.role))}</span>
            </span>
        </a>

        ${distinction ? `<p class="hi-distinction" ${i18nAttrs(distinction)}>${esc(L(distinction))}</p>` : ''}

        ${facts ? `<div class="hi-facts">${facts}</div>` : ''}

        <div class="hi-foot">
            <a class="gc-btn hi-btn" href="${href}"
               data-ar="صفحة المدرّب" data-en="Instructor page">صفحة المدرّب</a>
            ${linksHTML(inst)}
        </div>
    </article>`;
    }

    /**
     * The home page's instructor section. Reads INSTRUCTORS, so the day a
     * second instructor is added the grid grows on its own.
     *
     * With one instructor the grid is a single centred card rather than one
     * card stranded on the left of a three-column row — `.hi-grid` caps its
     * own width off the number of cards, so both cases look deliberate.
     */
    function renderHomeInstructors(el) {
        if (!el) return;
        const list = instructorList();
        if (!list.length) { el.innerHTML = ''; el.hidden = true; return; }
        el.hidden = false;
        el.className = 'hi-grid';

        // Repaint on `languagechange` like the other renderers: the card's
        // text is picked by L() at render time, so without this it would keep
        // whichever language was current when the page loaded.
        // ...and applyLanguageTo for the bits written as a literal with
        // data-ar/data-en (the button). i18n.js has already made its automatic
        // pass over the document by the time this markup exists, so without
        // this call those stay Arabic in English.
        const paint = () => {
            el.innerHTML = list.map(homeInstructorCardHTML).join('');
            if (typeof window.applyLanguageTo === 'function') window.applyLanguageTo(el);
        };
        paint();
        bindLanguage(el, paint);
    }

    /**
     * The instructor line on a course card: the round photo, then the name
     * with a short role under it.
     *
     * The photo comes FIRST in the markup, which is what puts it on the right
     * in Arabic and on the left in English — a flex row already follows the
     * document direction, so reading order is the only thing that has to be
     * right and there is no `left`/`right` rule anywhere.
     *
     * This is deliberately not `instructorBarHTML`. That one is a bordered
     * pill carrying the full role, sized for the wider layouts. On the card
     * the instructor sits flat on one edge of a row with the runtime on the
     * other, and the role line has to be the short version.
     */
    function cardInstructorHTML(inst) {
        if (!inst) return '<span></span>';   // keeps the runtime on its own edge
        const role = inst.roleShort || inst.role;
        return `
            <a class="gc-inst" href="/instructors?i=${encodeURIComponent(inst.slug)}">
                ${avatarHTML(inst, 'gc-avatar')}
                <span class="gc-inst-ident">
                    <span class="gc-inst-name">${esc(L(inst.name))}</span>
                    <span class="gc-inst-role" ${i18nAttrs(role)}>${esc(L(role))}</span>
                </span>
            </a>`;
    }

    /**
     * One course card — the same markup on the home page, on /courses and on
     * an instructor's page. There is never a second copy.
     *
     * The layout came from a reference the client sent: a green band across
     * the top, a big title, and one row under it with the instructor on one
     * side and the runtime on the other. That reference was a white card and
     * the card was built white; the client then asked for the surface to go
     * back to dark like the rest of the site.
     *
     * What the white surface was solving — "the green is taking everything" —
     * is still solved without it: the band and the clock icon are the only
     * green on the card. The version this replaced had a green glow on hover,
     * a green-tinted thumbnail, a green-filled button and a green avatar too.
     *
     * The reference has no course thumbnail; the client asked separately to
     * keep it, so it stays on top and the green band doubles as the seam
     * between it and the body. Dropping the image later means deleting the
     * `.gc-media` anchor and nothing else.
     */
    /**
     * The card thumbnail. A course with no artwork yet gets the same treatment
     * a track with no artwork gets — its track's icon on its family's gradient
     * — rather than `src="null"` and a broken-image glyph.
     */
    function courseMediaHTML(course, href) {
        const inner = course.image
            ? `<img src="${esc(course.image)}" alt="" loading="lazy" />`
            : (() => {
                const tr = track(course.track);
                const fam = tr ? family(tr.family) : null;
                const accent = fam ? fam.accent : 'gold';
                return `<span class="gc-media-ph tr-accent-${accent}" aria-hidden="true">
                    <i class="${esc(tr && tr.icon ? tr.icon : 'fa-solid fa-graduation-cap')}"></i>
                </span>`;
            })();

        // No link on an unreleased course — see the button below.
        return href
            ? `<a class="gc-media" href="${href}" tabindex="-1" aria-hidden="true">${inner}</a>`
            : `<span class="gc-media" aria-hidden="true">${inner}</span>`;
    }

    function courseCardHTML(course) {
        const inst = instructor(course.instructor);
        const soon = isSoon(course);
        // An unreleased course has no content page worth sending anyone to, so
        // the card does not link anywhere at all: not the thumbnail, not the
        // title, not the button. The button stays in place as an inert chip
        // reading "قريباً" so the card keeps its shape in the grid — hiding it
        // would leave this one card short next to its neighbours.
        const href = soon ? null : `/course-details?course=${encodeURIComponent(course.slug)}`;
        const title = L(course.title);

        // The reference writes the runtime as whole hours ("12 ساعة"), not as
        // the platform's "12h 3m". `hoursWord` handles the Arabic dual/plural.
        // With no runtime the slot says "قريباً" — never "0 ساعة", and never
        // an empty gap where a number should be.
        const mins = durationToMinutes(course.duration);
        const hours = soon
            ? SOON
            : (mins ? hoursWord(Math.round(mins / 60)) : { ar: course.duration, en: course.duration });

        const btn = soon
            ? `<span class="gc-btn gc-btn-soon" aria-disabled="true"
                     ${i18nAttrs(SOON)}>${esc(L(SOON))}</span>`
            : `<a class="gc-btn" href="${href}" data-ar="محتوى الكورس" data-en="Course content">محتوى الكورس</a>`;

        return `
    <article class="gc-card${soon ? ' is-soon' : ''}">
        ${courseMediaHTML(course, href)}
        <div class="gc-body">
            <h3 class="gc-title" ${i18nAttrs(course.title)}>${esc(title)}</h3>
            <div class="gc-meta">
                ${cardInstructorHTML(inst)}
                <span class="gc-hours${soon ? ' gc-hours-soon' : ''}">
                    <i class="fa-regular fa-${soon ? 'hourglass-half' : 'clock'}" aria-hidden="true"></i>
                    <span ${i18nAttrs(hours)}>${esc(L(hours))}</span>
                </span>
            </div>
            ${btn}
        </div>
    </article>`;
    }

    // ═══ Tracks ═════════════════════════════════════════════════

    /**
     * Keep a rendered container following the language.
     *
     * The guard is not just tidiness: /tracks rebuilds its entire body on
     * every `languagechange`, so the container this was bound to is a
     * detached node by the time the next event fires. Without the check each
     * language toggle would leave another listener behind, painting into a
     * node nobody can see. The listener removes itself the first time it
     * finds its element gone.
     */
    function bindLanguage(el, paint) {
        if (el.dataset.langBound) return;
        el.dataset.langBound = '1';
        const onLang = () => {
            if (!el.isConnected) {
                document.removeEventListener('languagechange', onLang);
                return;
            }
            paint();
        };
        document.addEventListener('languagechange', onLang);
    }

    /** "٣ كورسات" / "3 courses" — Arabic counts are not just N + a noun. */
    function coursesWord(n) {
        const ar = n === 1 ? 'كورس واحد'
            : n === 2 ? 'كورسين'
                : n <= 10 ? `${n} كورسات`
                    : `${n} كورس`;
        return { ar, en: n === 1 ? '1 course' : `${n} courses` };
    }

    function lessonsWord(n) {
        const ar = n === 1 ? 'درس واحد'
            : n === 2 ? 'درسين'
                : n <= 10 ? `${n} دروس`
                    : `${n} درس`;
        return { ar, en: n === 1 ? '1 lesson' : `${n} lessons` };
    }

    function hoursWord(n) {
        const ar = n === 1 ? 'ساعة' : n === 2 ? 'ساعتين' : n <= 10 ? `${n} ساعات` : `${n} ساعة`;
        return { ar, en: n === 1 ? '1 hour' : `${n} hours` };
    }

    /** "وكورس كمان قريباً" — the tail on a track that is partly released. */
    function soonMoreWord(n) {
        const ar = n === 1 ? 'وكورس كمان قريباً'
            : n === 2 ? 'وكورسين كمان قريباً'
                : `و${n} كورسات كمان قريباً`;
        return { ar, en: n === 1 ? '1 more coming soon' : `${n} more coming soon` };
    }

    const SOON = { ar: 'قريباً', en: 'Coming soon' };

    /**
     * Track artwork. The client has not sent the images yet, so `image: null`
     * draws a themed panel instead: the track's icon over a gradient tinted by
     * its family — gold for the deep tracks, blue for the applied ones. It is
     * a designed placeholder, not a grey box, and the two families read as
     * different at a glance which is the whole point of this page.
     *
     * Setting `image` in TRACKS swaps it for the real artwork with no change
     * to any HTML or CSS.
     */
    function trackThumbHTML(tr, extraClass) {
        const fam = family(tr.family);
        const accent = fam ? fam.accent : 'gold';
        const cls = `tr-thumb tr-accent-${accent}${extraClass ? ' ' + extraClass : ''}`;
        if (tr.image) {
            return `<span class="${cls}"><img src="${esc(tr.image)}" alt="" loading="lazy" /></span>`;
        }
        return `
        <span class="${cls} tr-thumb-ph" aria-hidden="true">
            <i class="${esc(tr.icon || 'fa-solid fa-route')}"></i>
        </span>`;
    }

    /**
     * One track card — used identically for both families so the visual
     * comparison the client asked for stays intact; only the accent differs.
     * `entry` is {track, stats} from trackListWithStats().
     */
    function trackCardHTML(entry) {
        const tr = entry.track;
        const st = entry.stats;
        const fam = family(tr.family);
        const accent = fam ? fam.accent : 'gold';
        const href = trackHref(tr.slug);

        // Nothing watchable — whether or not a course has been announced — is
        // one badge and no numbers. A "0 hours" on a card is worse than no
        // number at all.
        const nothingYet = st.empty || st.soon;

        // Some courses out, others still coming: say both, in that order.
        const soonTail = (!nothingYet && st.soonCount)
            ? `<span class="tr-meta-item tr-meta-soon">
                <i class="fa-regular fa-hourglass-half" aria-hidden="true"></i>
                <span ${i18nAttrs(soonMoreWord(st.soonCount))}>${esc(L(soonMoreWord(st.soonCount)))}</span>
            </span>`
            : '';

        const meta = nothingYet
            ? `<span class="tr-badge-soon" ${i18nAttrs(SOON)}>${esc(L(SOON))}</span>`
            : `
            <span class="tr-meta-item">
                <i class="fa-solid fa-graduation-cap" aria-hidden="true"></i>
                <span ${i18nAttrs(coursesWord(st.count))}>${esc(L(coursesWord(st.count)))}</span>
            </span>
            <span class="tr-meta-item">
                <i class="fa-regular fa-clock" aria-hidden="true"></i>
                <span ${i18nAttrs(hoursWord(st.hours))}>${esc(L(hoursWord(st.hours)))}</span>
            </span>${soonTail}`;

        const cta = nothingYet
            ? { ar: 'شوف المسار', en: 'See the track' }
            : { ar: 'افتح المسار', en: 'Open the track' };

        return `
    <a class="tr-card tr-accent-${accent}${nothingYet ? ' is-soon' : ''}" href="${href}">
        ${trackThumbHTML(tr, 'tr-thumb-card')}
        <span class="tr-card-body">
            <span class="tr-card-title" ${i18nAttrs(tr.name)}>${esc(L(tr.name))}</span>
            <span class="tr-card-short" ${i18nAttrs(tr.short)}>${esc(L(tr.short))}</span>
            <span class="tr-card-meta">${meta}</span>
            <span class="tr-card-cta" ${i18nAttrs(cta)}>${esc(L(cta))}</span>
        </span>
    </a>`;
    }

    function trackSkeletonHTML(count) {
        let out = '';
        for (let i = 0; i < count; i++) {
            out += `
    <div class="tr-card tr-card-skeleton" aria-hidden="true">
        <div class="tr-thumb gc-sk"></div>
        <div class="tr-card-body">
            <div class="gc-sk gc-sk-line gc-sk-title"></div>
            <div class="gc-sk gc-sk-line gc-sk-short"></div>
            <div class="gc-sk gc-sk-line gc-sk-short"></div>
        </div>
    </div>`;
        }
        return out;
    }

    /**
     * Fill a container with the track cards of one family. Same
     * skeleton → cards → re-render-on-languagechange contract as the course
     * grid, so both grids behave the same way on every page.
     */
    function renderTrackCards(el, familySlug) {
        if (!el) return Promise.resolve([]);
        el.classList.add('tr-grid');
        el.innerHTML = trackSkeletonHTML(trackList(familySlug).length);

        const paint = () => trackListWithStats(familySlug).then(entries => {
            el.innerHTML = entries.length
                ? entries.map(trackCardHTML).join('')
                : emptyHTML();
            return entries;
        });

        return paint().then(entries => {
            bindLanguage(el, paint);
            return entries;
        });
    }

    /**
     * The home-page teaser: one panel per family with its one-line definition
     * and the tracks inside it as chips. Deliberately NOT the comparison —
     * that lives on /tracks. Built from the same FAMILIES/TRACKS data, so the
     * home page can never list a track the tracks page does not have.
     */
    function familyTeaserHTML(fam, entries) {
        const chips = entries.map(e => {
            // Same three-state rule as the track card: a track whose only
            // courses are unreleased is still "قريباً", not "1 course".
            const soon = e.stats.empty || e.stats.soon;
            const label = soon
                ? { ar: `${L(e.track.name)} — قريباً`, en: `${L(e.track.name)} — soon` }
                : {
                    ar: `${e.track.name.ar} · ${coursesWord(e.stats.count).ar}`,
                    en: `${e.track.name.en} · ${coursesWord(e.stats.count).en}`
                };
            return `<a class="tr-chip${soon ? ' is-soon' : ''}" href="${trackHref(e.track.slug)}"
                       ${i18nAttrs(label)}>${esc(L(label))}</a>`;
        }).join('');

        return `
    <article class="tr-family tr-accent-${fam.accent}">
        <div class="tr-family-head">
            <span class="tr-family-icon" aria-hidden="true"><i class="${esc(fam.icon)}"></i></span>
            <div class="tr-family-ident">
                <h3 class="tr-family-name" ${i18nAttrs(fam.name)}>${esc(L(fam.name))}</h3>
                <span class="tr-family-tag" ${i18nAttrs(fam.tagline)}>${esc(L(fam.tagline))}</span>
            </div>
        </div>
        <p class="tr-family-line" ${i18nAttrs(fam.oneLine)}>${esc(L(fam.oneLine))}</p>
        <div class="tr-chips">${chips}</div>
    </article>`;
    }

    function renderFamilyTeaser(el) {
        if (!el) return Promise.resolve([]);
        el.classList.add('tr-family-grid');

        const paint = () => Promise.all(familyList().map(fam =>
            trackListWithStats(fam.slug).then(entries => familyTeaserHTML(fam, entries))
        )).then(html => { el.innerHTML = html.join(''); });

        return paint().then(() => bindLanguage(el, paint));
    }

    /**
     * The two-column comparison. Rendered twice into the same container: as a
     * real table on wide screens and as one stacked block per family on
     * phones, because a 2-column table of long Arabic sentences is unreadable
     * at 360px. Both are built from the same COMPARE_ROWS, so they cannot say
     * different things — CSS picks which one is visible.
     */
    function compareHTML() {
        const fams = familyList();

        const head = fams.map(f => `
            <th class="tr-cmp-head tr-accent-${f.accent}">
                <span class="tr-cmp-head-icon" aria-hidden="true"><i class="${esc(f.icon)}"></i></span>
                <span class="tr-cmp-head-name" ${i18nAttrs(f.name)}>${esc(L(f.name))}</span>
                <span class="tr-cmp-head-tag" ${i18nAttrs(f.tagline)}>${esc(L(f.tagline))}</span>
            </th>`).join('');

        const rows = COMPARE_ROWS.map(row => `
        <tr>
            <th class="tr-cmp-label" scope="row">
                <i class="${esc(row.icon)}" aria-hidden="true"></i>
                <span ${i18nAttrs(row.label)}>${esc(L(row.label))}</span>
            </th>
            ${fams.map(f => `<td ${i18nAttrs(f[row.key])}>${esc(L(f[row.key]))}</td>`).join('')}
        </tr>`).join('');

        const table = `
    <div class="tr-cmp-scroll">
        <table class="tr-cmp">
            <thead>
                <tr>
                    <th class="tr-cmp-corner">
                        <span data-ar="المقارنة" data-en="Side by side">المقارنة</span>
                    </th>
                    ${head}
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    </div>`;

        const stacked = fams.map(f => `
    <section class="tr-cmp-stack tr-accent-${f.accent}">
        <header class="tr-cmp-stack-head">
            <span class="tr-cmp-head-icon" aria-hidden="true"><i class="${esc(f.icon)}"></i></span>
            <span class="tr-cmp-head-name" ${i18nAttrs(f.name)}>${esc(L(f.name))}</span>
            <span class="tr-cmp-head-tag" ${i18nAttrs(f.tagline)}>${esc(L(f.tagline))}</span>
        </header>
        <dl class="tr-cmp-stack-list">
            ${COMPARE_ROWS.map(row => `
            <dt><i class="${esc(row.icon)}" aria-hidden="true"></i>
                <span ${i18nAttrs(row.label)}>${esc(L(row.label))}</span></dt>
            <dd ${i18nAttrs(f[row.key])}>${esc(L(f[row.key]))}</dd>`).join('')}
        </dl>
    </section>`).join('');

        return table + `<div class="tr-cmp-stacked">${stacked}</div>`;
    }

    /** The two "what is a X track" explainer panels above the comparison. */
    function familyExplainerHTML() {
        return familyList().map(f => `
    <article class="tr-explain tr-accent-${f.accent}">
        <span class="tr-explain-icon" aria-hidden="true"><i class="${esc(f.icon)}"></i></span>
        <h3 class="tr-explain-name" ${i18nAttrs(f.name)}>${esc(L(f.name))}</h3>
        <p class="tr-explain-line" ${i18nAttrs(f.oneLine)}>${esc(L(f.oneLine))}</p>
        <p class="tr-explain-eg" ${i18nAttrs(f.example)}>${esc(L(f.example))}</p>
    </article>`).join('');
    }

    /** Grey card while the API answers — one per course we know we will show. */
    function skeletonHTML(count) {
        let out = '';
        for (let i = 0; i < count; i++) {
            out += `
    <article class="gc-card gc-card-skeleton" aria-hidden="true">
        <div class="gc-media gc-sk"></div>
        <div class="gc-body">
            <div class="gc-sk gc-sk-line gc-sk-title"></div>
            <div class="gc-sk-meta">
                <div class="gc-sk gc-sk-inst"></div>
                <div class="gc-sk gc-sk-line gc-sk-short"></div>
            </div>
            <div class="gc-sk gc-sk-btn"></div>
        </div>
    </article>`;
        }
        return out;
    }

    function emptyHTML() {
        return `
    <div class="gc-empty">
        <i class="fa-solid fa-graduation-cap" aria-hidden="true"></i>
        <p data-ar="مفيش كورسات معروضة دلوقتي. جرّب تعمل ريفريش بعد شوية."
           data-en="No courses to show right now. Try refreshing in a moment.">مفيش كورسات معروضة دلوقتي. جرّب تعمل ريفريش بعد شوية.</p>
    </div>`;
    }

    /**
     * Fill a container with course cards: skeleton → cards, or the empty state
     * if the list comes back with nothing. Re-runs itself on `languagechange`
     * so the cards follow the language like static markup does.
     */
    function renderCourseGrid(el, opts) {
        if (!el) return Promise.resolve([]);
        const o = opts || {};
        el.classList.add('gc-grid');
        el.innerHTML = skeletonHTML(o.limit || COURSES.length);

        // Most of the card is written in the current language by `L()` at
        // render time, but the "محتوى الكورس" button and the empty state are
        // plain data-ar/data-en markup like the rest of the site. i18n.js has
        // already made its page-load pass by the time this paints, so those
        // two have to be handed to it explicitly or they stay Arabic on the
        // English site.
        const paint = html => {
            el.innerHTML = html;
            if (typeof window.applyLanguageTo === 'function') window.applyLanguageTo(el);
        };

        return load().then(list => {
            const shown = o.limit ? list.slice(0, o.limit) : list;
            paint(shown.length ? shown.map(courseCardHTML).join('') : emptyHTML());
            if (!el.dataset.langBound) {
                el.dataset.langBound = '1';
                document.addEventListener('languagechange', () => {
                    load().then(l2 => {
                        const s2 = o.limit ? l2.slice(0, o.limit) : l2;
                        paint(s2.length ? s2.map(courseCardHTML).join('') : emptyHTML());
                    });
                });
            }
            return shown;
        });
    }

    /**
     * Fill a totals bar (`[data-total="courses"]` / `[data-total="hours"]`)
     * with the catalog-wide figures and reveal it.
     */
    function renderTotals(el) {
        if (!el) return Promise.resolve(null);
        return load().then(list => {
            const t = totals(list);
            const set = (key, value) => {
                const node = el.querySelector(`[data-total="${key}"]`);
                if (node) node.textContent = value;
            };
            set('courses', t.courses);
            set('hours', t.hours + '+');
            set('lessons', t.lessons);
            el.classList.remove('is-pending');
            return t;
        });
    }

    // ─── Auto-init ──────────────────────────────────────────────
    // Any page that wants the course grid just puts `<div id="coursesGrid">`
    // (and optionally a totals bar) in its markup and loads this file — the
    // home page and /courses do exactly that and share this one code path,
    // so there is no second copy of the wiring to drift.
    function autoInit() {
        renderCourseGrid(document.getElementById('coursesGrid'));
        renderTotals(document.getElementById('coursesTotals'));
        // The home page's tracks teaser — same deal: drop the container in and
        // this fills it, so the home page holds no track data of its own.
        renderFamilyTeaser(document.getElementById('trackFamilies'));
        // Same deal for the home page's instructor section.
        renderHomeInstructors(document.getElementById('homeInstructors'));
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInit);
    } else {
        autoInit();
    }

    window.GhawyCatalog = {
        API_BASE,
        INSTRUCTORS, TRACKS, COURSES, FAMILIES, COMPARE_ROWS,
        L, esc, i18nAttrs, mediaURL,
        durationToMinutes, minutesToDuration, isSoon,
        instructor, track, family,
        load, courseBySlug, lessonsFor, totals,
        coursesByInstructor, instructorList, courseCountFor, soonCountFor,
        yearsLineFor,
        familyList, trackList, trackHref,
        coursesInTrack, trackStats, trackListWithStats,
        coursesWord, lessonsWord, hoursWord, SOON,
        courseCardHTML, instructorCardHTML, linksHTML,
        homeInstructorCardHTML, renderHomeInstructors,
        instructorBarHTML, factsHTML, clientsHTML,
        introVideoHTML, courseVideoHTML,
        trackThumbHTML, trackCardHTML, trackSkeletonHTML,
        renderTrackCards, renderFamilyTeaser,
        compareHTML, familyExplainerHTML,
        skeletonHTML, emptyHTML, renderCourseGrid, renderTotals,
        avatarHTML,
    };
})();
