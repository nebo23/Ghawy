// ═══ GHAWY CATALOG DATA — the static half of the catalog, on its own ═══
//
// INSTRUCTORS, FAMILIES, TRACKS and COURSES used to live inside catalog.js
// next to the renderers that draw the public site. That was fine until the
// members' courses page (dashboard-courses.html) needed the same facts — which
// course is taught by whom, which track it belongs to — to power its search
// and filters.
//
// It could not simply load catalog.js: that file auto-renders the marketing
// cards into `#coursesGrid` on DOMContentLoaded, and the members' page has a
// grid by that exact id. Loading it there wiped the member cards and replaced
// them with the public ones.
//
// So the DATA lives here and the RENDERING stays in catalog.js. This file
// draws nothing, touches no DOM and has no side effects beyond publishing
// `window.GhawyCatalogData`. Load it BEFORE catalog.js on the public pages;
// load it ALONE on the community pages.
//
// Editing rules are unchanged — every comment below travelled with its block
// and still describes the same decisions.

(function () {
    'use strict';

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
            // Everything a member might type to mean this person: the Arabic
            // spelling, the English one, the handle, the bare surname. The
            // community search matches against these as well as `name`, which
            // is the only reason typing "الطلخاوي" finds a course filed under
            // the handle "Talkhawy".
            //
            // NOTE FOR THE CLIENT: for `ofa` and `talkhawy` the display name
            // IS the handle — nobody here knows their real names (see the
            // block above). The Arabic entries below are the reasonable ways
            // someone would transliterate that handle, NOT a claim about how
            // they spell their own name. Send the official names and they go
            // in `name` first, here second.
            aliases: ['محمد صلاح', 'mohamed salah', 'mohammed salah', 'صلاح', 'salah', 'مؤسس غاوي', 'ghawy'],
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
                tiktok: 'https://www.tiktok.com/@ghawy.ai',
                facebook: 'https://www.facebook.com/profile.php?id=61591378479904',
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
            aliases: ['اوفا', 'أوفا', 'ofa', 'ofapsd'],
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
            aliases: ['الطلخاوي', 'طلخاوي', 'talkhawy', 'el talkhawy', 'al talkhawy', 'tlkhawy'],
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
        // Claude Code was a course inside the automation track until the client
        // said it is a track of its own, not one stop on someone else's road.
        //
        // `applied` and not `deep`: the deep family is about making AI the
        // craft itself, while this is one tool pointed at work you already do.
        // The one place the family does not fit is its "no technical
        // background" line — this track does assume you already work with AI —
        // so `startsFrom` says that outright rather than letting the family
        // blurb speak for it.
        //
        // Everything below is drawn from the seven lessons the platform already
        // has (course id 12): CLAUDE.md, context management, MCPs, Skills,
        // Agents, and Use Cases & Build. Nothing here claims more than that.
        'claude-code': {
            slug: 'claude-code',
            family: 'applied',
            icon: 'fa-solid fa-terminal',
            image: null,
            name: { ar: 'كلود كود', en: 'Claude Code' },
            short: { ar: 'الـ AI بيشتغل جوه مشروعك', en: 'AI working inside your project' },
            about: {
                ar: 'مسار كامل على كلود كود: تشغّله على مشروعك، تظبّطه بملف CLAUDE.md، تدير الكونتكست بتاعه، وتوصّله بأدواتك عن طريق الـ MCPs والـ Skills والـ Agents عشان ينفّذ شغل حقيقي مش بس يرد عليك.',
                en: 'A full track on Claude Code: run it on your own project, set it up with a CLAUDE.md, manage its context, and wire it to your tools through MCPs, Skills and Agents so it does real work instead of just answering you.'
            },
            forWho: {
                ar: 'أي حد بيبني حاجة — كود، أوتوميشن، أدوات داخلية — وعايز الـ AI يشتغل جوه شغله فعلاً مش في شباك دردشة لوحده.',
                en: 'Anyone who builds things — code, automations, internal tools — and wants AI working inside the work itself rather than in a chat window beside it.'
            },
            startsFrom: {
                ar: 'مش من الصفر. المسار ده بيفترض إنك بتستخدم الـ AI بالفعل ومرتاح في التعامل مع الملفات والتيرمينال.',
                en: 'Not from zero. This track assumes you already use AI and are comfortable with files and a terminal.'
            },
            outcomes: [
                { ar: 'تشغّل كلود كود على مشروعك وتخليه يفهم شغلك من ملف CLAUDE.md', en: 'Run Claude Code on your own project and have it learn your work from a CLAUDE.md' },
                { ar: 'تدير الكونتكست بحيث ياخد باله من اللي يهم ويسيب اللي مش مهم', en: 'Manage its context so it holds on to what matters and drops what does not' },
                { ar: 'توصّله بأدواتك الخارجية عن طريق الـ MCPs', en: 'Connect it to your external tools through MCPs' },
                { ar: 'تبني Skills و Agents تنفّذ الخطوات اللي بتعيدها كل مرة', en: 'Build Skills and Agents that carry out the steps you repeat every time' },
                { ar: 'تنفّذ حالات استخدام حقيقية من أول الفكرة لحد ما تشتغل', en: 'Take real use cases from the idea through to something that runs' },
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
    // `keywords` is search-only: Arabic, English and franco spellings a member
    // might actually type. The community courses page scores a course on its
    // title, its instructor, its track AND these — so "اتوميشن" (misspelt, no
    // و) still lands on the automation courses. Nothing renders them.
    const COURSES = [
        {
            slug: 'ai-foundations',
            courseId: 5,
            title: { ar: 'أساسيات الذكاء الاصطناعي', en: 'AI Foundations' },
            keywords: ['اساسيات', 'أساسيات', 'foundations', 'basics', 'مبتدئ', 'من الصفر', 'ai', 'ذكاء اصطناعي'],
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
            keywords: ['وكالة', 'agency', 'aaa', 'بيزنس', 'business', 'اوتوميشن اجنسي'],
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
            keywords: ['برومبت', 'prompt', 'هندسة البرومبت', 'prompting', 'برومبتات'],
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
            keywords: ['اوتوميشن', 'أوتوميشن', 'automation', 'n8n', 'make', 'workflow', 'ورك فلو'],
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
            keywords: ['مشاريع', 'projects', 'انظمة', 'systems', 'practical', 'عملي', 'تطبيقي'],
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
            keywords: ['عملاء', 'clients', 'sales', 'مبيعات', 'اكتساب', 'اكتساب العملاء', 'كلاينتس'],
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
        // It sat in `automation` until the client said Claude Code is a course
        // AND a track of its own, so it is now the only course in the
        // `claude-code` track. Automation is unaffected by the move: it still
        // holds the contiguous 2→5 run plus Client Acquisition, which is the
        // whole of what the client described that track as.
        {
            slug: 'claude-code',
            courseId: 12,
            title: { ar: 'كلود كود', en: 'Claude Code' },
            keywords: ['كلود', 'claude', 'claude code', 'كلود كود', 'mcp', 'agents', 'skills', 'terminal', 'تيرمينال'],
            image: './imgs/course7.jpg',
            lessons: 7,
            duration: '5h 56m',
            track: 'claude-code',
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
        // `memberCourseId` — NOT `courseId`.
        //
        // These two courses are published in the platform (rows 14 and 15), so
        // the members' area lists them and needs to know who teaches them and
        // which track they are in. The public site must NOT learn that: a
        // course here becomes "released" the moment it has a `courseId`,
        // because load() then merges the live runtime over it and isSoon()
        // stops being true — the home page, /courses and the track totals would
        // all flip to "available" without anybody asking for it.
        //
        // So the join key for the members' area is a field of its own, read
        // only by course-card.js. Giving one of these a real `courseId` stays
        // the deliberate act that releases it on the public site.
        {
            slug: 'ai-thumbnails',
            memberCourseId: 15,
            title: { ar: 'الثامبنيلز بالذكاء الاصطناعي', en: 'AI Thumbnails' },
            keywords: ['ثامبنيل', 'ثامبنيلز', 'thumbnail', 'thumbnails', 'يوتيوب', 'youtube', 'تصميم', 'design'],
            image: null,
            track: 'ai-thumbnails',
            instructor: 'ofa',
        },
        {
            slug: 'machine-learning',
            memberCourseId: 14,
            title: { ar: 'Machine Learning', en: 'Machine Learning' },
            keywords: ['machine learning', 'ml', 'ماشين ليرنينج', 'تعلم الالة', 'تعلم الآلة', 'موديل', 'models', 'نماذج', 'داتا', 'data'],
            image: null,
            track: 'machine-learning',
            instructor: 'talkhawy',
        },
    ];

    // The public site reads these through catalog.js, which assigns them
    // straight off this object; the community courses page reads this object
    // directly. One definition, two consumers.
    window.GhawyCatalogData = { INSTRUCTORS, TRACKS, COURSES, FAMILIES };
})();
