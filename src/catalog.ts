import type { Series, Work, WorkKind } from "./types";

export const series: Series[] = [
  {
    id: "kruptos",
    title: "The Kruptos Protocol",
    roman: "III",
    tagline: "Volume Three · Classified Light",
    description:
      "The sealed third movement of The Return of Melchizedek — a protocol of hidden things, written for those who can bear them.",
    cover: "/art/kruptos.jpg",
    accent: "#c9a227",
  },
  {
    id: "trom",
    title: "The Return of Melchizedek",
    tagline: "Priest of the Most High",
    description:
      "A long arc through the order that has neither beginning of days nor end of life — bread, wine, thrones, and the men from the Arabah.",
    cover: "/art/melchizedek.jpg",
    accent: "#d4af37",
  },
  {
    id: "noah",
    title: "The Days of Noah",
    tagline: "Watchers · Courts · Blood",
    description:
      "From the fall of the sons of God to the courts of heaven: watchers, imaginations of Lucifer, the evil kingdom, and the blood of Jesus.",
    cover: "/art/noah.jpg",
    accent: "#8b6b2e",
  },
  {
    id: "abraham",
    title: "Abrahamic Series",
    tagline: "The Friend of God",
    description:
      "Two seasons through the mysteries of the fathers — coats of many colours, Mamre, famine, compass points, and the creativity of the Word.",
    cover: "/art/abraham.jpg",
    accent: "#c47a3a",
  },
  {
    id: "melchizedek",
    title: "Mystery of Melchizedek",
    tagline: "Abrahamic · Season II · Part 10",
    description:
      "A seventeen-part descent into priesthood, the world beneath, spirit cities, the forgotten Adam, and the genesis of the high priest.",
    cover: "/art/melchizedek.jpg",
    accent: "#b8860b",
  },
  {
    id: "heis",
    title: "Heis Series",
    tagline: "The Seed of God",
    description:
      "Oneness, seed, and the architecture of glory — a nine-part unveiling of what it means that He and we are one.",
    cover: "/art/heis.jpg",
    accent: "#e8c872",
  },
  {
    id: "unmasking",
    title: "Unmasking The Devil",
    tagline: "Flesh · Fall · Zion",
    description:
      "Aliens of glory, the apocalypse, dealing with the flesh, and the mountain we have come unto — a series of unmaskings.",
    cover: "/art/unmasking.jpg",
    accent: "#9a3b3b",
  },
  {
    id: "word",
    title: "Word of God Series",
    tagline: "Mind · Heart · Word",
    description:
      "Eating, hiding, sleeping, and standing with the Word — how the sure word of prophecy takes residence in a man.",
    cover: "/art/word.jpg",
    accent: "#cfc09a",
  },
  {
    id: "meditation",
    title: "Meditation Series",
    tagline: "The Inner Course",
    description:
      "The road to meditation and the course of it — a quiet curriculum for those learning to remain.",
    cover: "/art/meditation.jpg",
    accent: "#7a8aa0",
  },
  {
    id: "comics",
    title: "Comic Book Issues",
    tagline: "Illustrated Mysteries",
    description:
      "Graphic teachings from the Bible Secrets universe, including Church Witchcraft Issue #1 and the characters primer.",
    cover: "/art/comic.jpg",
    accent: "#c45c26",
  },
  {
    id: "qa",
    title: "Questions & Answers",
    tagline: "The Open Court",
    description:
      "Three sessions of Bible Secrets Q&A — the questions the house asked, and the answers that followed.",
    cover: "/art/noah.jpg",
    accent: "#6e5a3a",
  },
  {
    id: "others",
    title: "The Outer Court",
    tagline: "Standalone Teachings",
    description:
      "Ascension, communion, Leviticus, the sword of the Spirit, and guest voices — works that stand alone in the vault.",
    cover: "/art/hero.jpg",
    accent: "#a0895a",
  },
];

const w = (
  driveId: string,
  title: string,
  seriesId: string,
  kind: WorkKind,
  extra: Partial<Work> = {},
): Work => ({
  id: driveId,
  driveId,
  title,
  seriesId,
  kind,
  ...extra,
});

export const works: Work[] = [
  w("10swHqoEyakOyTEBDZldDBgfsSfz6eZpg", "The Kruptos Protocol", "kruptos", "pdf", {
    featured: true,
    part: 3,
    blurb: "TRoM Volume 3 — the sealed protocol.",
  }),

  w("1x-xO1nbwsnX2tiYfZ4a3MLBrPrp_g210", "The Return of Melchizedek I", "trom", "pdf", {
    featured: true,
    part: 1,
  }),
  w("1xAE1L4bQKphsTXd38Vr-_gAAal4gqbtG", "The Return of Melchizedek II", "trom", "pdf", { part: 2 }),
  w("1wtaegN0CmOmxqw1ba_IEGikPEnFOA_To", "The Return of Melchizedek III", "trom", "pdf", { part: 3 }),
  w("1xAWtODxIzH76PHhhDISr5KYPpsXn2Gue", "The Return of Melchizedek IV", "trom", "pdf", { part: 4 }),
  w("1wuK4CuGlYYsXG2RS64OpdQPH4_nHaorl", "The Return of Melchizedek V", "trom", "pdf", { part: 5 }),
  w("1wn3z31tzvbLC7idNMq57UH1W7rL_qy8G", "The Return of Melchizedek IX", "trom", "pdf", { part: 9 }),
  w("15fMnvwO-kBcvpmDEAQBZgK9T5Gh4UpHw", "Volume X — Lab Session 4", "trom", "pdf", { part: 10 }),
  w("15doLWArGMXtGBz71KoNVFW7rfz4nQ_iU", "The Return of Melchizedek XI", "trom", "pdf", { part: 11 }),
  w("15V63ltE8AYvwFug9eW_DKyT_KzppSoVV", "The Return of Melchizedek XII", "trom", "pdf", { part: 12 }),
  w("15TBIwKG8KfMzvemGUTop46jgNaIoPc38", "The Return of Melchizedek XIII", "trom", "pdf", { part: 13 }),
  w("1EiLo9RkriW8IsasYHuQvzjfeWgJe8mYi", "The Return of Melchizedek XIV", "trom", "pdf", { part: 14 }),
  w("1Eq3hyudLSw1MWKeP3s35BllDGSxQPfgo", "The Return of Melchizedek XV", "trom", "pdf", { part: 15 }),

  w("1ei2_PtiYgO3e62xiGHlZ3ZwgSjOjGf1d", "The Fall of The Sons of God I", "noah", "pdf", {
    featured: true,
    part: 1,
  }),
  w("1gWRaPuGpz4MJfaIM-QizVJSBJxMmGSJ-", "Noah & Melchizedek", "noah", "pdf", { part: 2 }),
  w("1i27cxulmG1OQnZrMlfAiPJJbd7pCRj-c", "The Gates of Hell I", "noah", "pdf", { part: 3 }),
  w("1V69YDwOqLipJUPp9rxbwKAsc2jVkGit_", "The Gates of Hell II — The Sword of Goliath", "noah", "pdf", { part: 4 }),
  w("1-eCYkQ6FAmPv-kaD_HVSvB4fvJ6Qt0o9", "The Gates of Hell III — Before The Tomb", "noah", "pdf", { part: 5 }),
  w("1-Z3XauHvGWss0aoZWOvsVhCIMBW4OcIw", "The Fall of The Sons of God II", "noah", "pdf", { part: 6 }),
  w("1-YcoXTAWP8CTDD-7OnrV0mgHugUZYnxk", "The Ministry of The Watchers", "noah", "pdf", { part: 7 }),
  w("1S8XpIyJYTj0bFRafCHSF9cxKAARb1Rop", "The Ministry of the Watchers 2.0", "noah", "pdf", { part: 8 }),
  w("1ZwhyXNy0zP-shry4cs_Ca4UgVTOSlg9f", "The Ministry of the Watchers III", "noah", "pdf", { part: 9 }),
  w("1ZxXXDrs6s2mIIhy6qEIt09K3xV28HCAd", "The Ministry of the Watchers IV", "noah", "pdf", { part: 10 }),
  w("1Zy8jDTjPh3F70OtIzPU68rplsbNAempL", "The Ministry of The Watchers V", "noah", "pdf", { part: 11 }),
  w("1_0PR1pMdNG4ypYhnZKKqBxquaLp47yjn", "The Imaginations of Lucifer I", "noah", "pdf", { part: 12 }),
  w("1_2RABbRmmO2lZVAqHuz5vXNwd8CS3x2F", "The Imaginations of Lucifer II — Stars & Morningstars", "noah", "pdf", { part: 13 }),
  w("1_56TPZtCZECIObiN2zj-f03h9D4a4igD", "The Imaginations of Lucifer III", "noah", "pdf", { part: 14 }),
  w("1_8PN9DX_67MeSshttZKD7xRG3zhxO3_1", "The Imaginations of Lucifer IV", "noah", "pdf", { part: 15 }),
  w("1_98ghtiRSnqL77lP_hyQEVFMQZxLPQ6K", "The Imaginations of Lucifer V", "noah", "pdf", { part: 16 }),
  w("16YCIeFuCOyZnVGAC8KZIW1UxDClcJ2ll", "The Evil Kingdom I", "noah", "pdf", { part: 17 }),
  w("16euMpCcy99HK1mzWZyaZl71a8Cbr3zbs", "The Evil Kingdom II", "noah", "pdf", { part: 18 }),
  w("16jGZMQIc61qjWctbveRg0hwSp2C5vf4g", "The Evil Kingdom III", "noah", "pdf", { part: 19 }),
  w("1OZZGGeCqn36tRW8DEvMqQUn_GsOQIA30", "The Courts of Heaven I", "noah", "pdf", { part: 20 }),
  w("14_Wx7LPnNIXFOyLuvE-gKRc37VwYddsq", "The Courts of Heaven II", "noah", "pdf", { part: 21 }),
  w("14ZG0eqFrissveJHjHQgdPOSCF3f49Vlp", "Engaging The Courts of Heaven", "noah", "pdf", { part: 22 }),
  w("16e8wVDs4QqMDf6SKSB_WA01IECeBpOKN", "Engaging The Courts of Heaven IV", "noah", "pdf", { part: 23 }),
  w("15DRQUYTppgUAGPD1AUG6zj0EmlFaZPuI", "Seven Days In The Courts of Heaven", "noah", "pdf", { part: 24 }),
  w("14dQufv2R-2iN43Htc5s3u9gCzhDeqZrh", "Engaging The Courts — Giving", "noah", "pdf", { part: 25 }),
  w("14fr7RqsN1ttiANvBqNqL_f9UpZ2NQhjf", "Engaging The Courts — The Bride", "noah", "pdf", { part: 26 }),
  w("16dFcUWT9jTdrdHlbGXHg9Ouhl5-yEaf4", "Court Session For Families I", "noah", "pdf", { part: 27 }),
  w("1gjo6LLNmF6yVmRpZG4T3QAsQEJYrLgfW", "The Bride", "noah", "pdf", { part: 28 }),
  w("14rZ4tDluxw9lYc2jBJrkrlugj0t0vVEh", "Court Session For Families II", "noah", "pdf", { part: 29 }),
  w("1MNIe-q9qMzXBsDjm9ERdj1b5uMfy_cxz", "The Blood of Jesus I", "noah", "pdf", { part: 30 }),
  w("1MScKVBeBR7cXUsCQh9Z05Hi9E7fsZKVH", "The Blood of Jesus II", "noah", "pdf", { part: 31 }),
  w("1MOBS0L7IDwNUwnDU-uHILTe1ZcPIW98d", "The Blood of Jesus III", "noah", "pdf", { part: 32 }),
  w("1MTq8wVIrgvnTIVUv976Olp0NjAE0uCXs", "The Blood of Jesus V", "noah", "pdf", { part: 34 }),
  w("1MVjMeh2OXUzi36kqLF_gRv5cqzP3EV3k", "The Ministry of Angels", "noah", "pdf", { part: 35 }),

  w("1Ol63qVnm5UgFr8WHIvITOzaW9uskkU1W", "Bible Secrets Q&A I", "qa", "pdf", { part: 1 }),
  w("1Os-_zUmZIJxvB31pKMquVr8DaXnSPrPL", "Bible Secrets Q&A II", "qa", "pdf", { part: 2 }),
  w("1OwV8Fql5d7j1mRefrEGsd-0I0QwB4saI", "Bible Secrets Q&A III", "qa", "pdf", { part: 3 }),

  w("1-hSi3lrLpKU3tg7FPReZDdbBmih4PwIJ", "Season I · Part 1", "abraham", "pdf", { season: "I", part: 1 }),
  w("109JpnvROoooKmcbqdwgdbsHFt4ubHacj", "Season I · Part 2", "abraham", "pdf", { season: "I", part: 2 }),
  w("1-n-BLovk-LO91n8uEWxn9MqpwpQXA9S-", "Season I · Part 3", "abraham", "pdf", { season: "I", part: 3 }),
  w("10HJUHbIsGBCKuQwrZppbavOx9Ea_rpoM", "Season I · Part 4", "abraham", "pdf", { season: "I", part: 4 }),
  w("1-n8MVa1eTFBeNwYHdEGjKUFfuKCr7BCx", "Season I · Part 5", "abraham", "pdf", { season: "I", part: 5 }),
  w("10TPxIDOnAy9_7Xi-VHFoTjM6VN69-Hqp", "Season I · Part 6", "abraham", "pdf", { season: "I", part: 6 }),
  w("100Byrp9Jl-g0wYCsm-vfgdIs-iRn5sNk", "Season I · Part 7", "abraham", "pdf", { season: "I", part: 7 }),
  w("10WWZlwnRIZak5vfLHzPvAyZjsPaCwKOG", "Season I · Part 8", "abraham", "pdf", { season: "I", part: 8 }),
  w("1-UA_jaIEcGoDrfAOQXddbyo3KsDvdrVZ", "Season I · Part 9", "abraham", "pdf", { season: "I", part: 9 }),
  w("1NiRq31q3VWuGC9o2fXyMt9D6Q0Kajopc", "Season I · Part 10", "abraham", "pdf", { season: "I", part: 10 }),
  w("10AdAVheTj5zoKn4pjPyUkrffuV3CzsPe", "Season I · Part 11", "abraham", "pdf", { season: "I", part: 11 }),
  w("1NkPdYEq-VPQMHLc1Jo3lqORNVER_4RJx", "Season I · Part 12", "abraham", "doc", { season: "I", part: 12 }),
  w("1016Wj61CbLfdxmNyuIP5c_2LQY90SdXi", "Season I · Part 13", "abraham", "pdf", { season: "I", part: 13 }),
  w("1-iuhOJgeYpFZH7ceuZe8DgxT0ZPqY4vp", "Season I · Part 14", "abraham", "pdf", { season: "I", part: 14 }),
  w("1-WS7K4y2-i24olu6C2bBAIU3Frdl8J33", "Season I · Part 14 Extension", "abraham", "pdf", { season: "I", part: 14.5 }),

  w("11o90zfh2iNxoAiqoi4crJcomV_6QAWS1", "Treasures of the Glorious Rest I", "abraham", "doc", {
    season: "pre",
    part: 0,
  }),
  w("115LQsgeg9mhWPSQz3lpRmZrMnZ-q9bzZ", "Treasures of The Glorious Rest II", "abraham", "doc", {
    season: "pre",
    part: 0.5,
  }),

  w("11mSlY-Hc571oZ9mPWnmSSGf_DFMPvnt1", "Errors Of The Fathers", "abraham", "doc", { season: "II", part: 1 }),
  w("11eCuWOnEo0RMZQgUw2P-DReUMl5W3L7r", "Coat Of Many Colours", "abraham", "doc", { season: "II", part: 2 }),
  w("11kFv1aGvxe73Yr83k35urEqc0DuMcP6w", "Red Green Blue", "abraham", "doc", { season: "II", part: 3 }),
  w("11kjipYvAeKNb3cFvNJ6qfkN5AdmTn3_C", "The Days Of Enosh", "abraham", "doc", { season: "II", part: 4 }),
  w("11htebWepptm6jzyFXMkxOm3-9Ex8bkC3", "The Lord Had Said", "abraham", "pdf", { season: "II", part: 5 }),
  w("11ovWPQw4C4ROgKmPyzUjFKa0EBVdQnsQ", "And The Lord Appeared Unto Abram", "abraham", "doc", { season: "II", part: 6 }),
  w("11Yxx7denTdxbH9FbbqOwEO7Lcs_Gscah", "Mystery of The Great Famine", "abraham", "pdf", { season: "II", part: 7 }),
  w("11kRUZOdomzq6ULBd9ZucFoaXM71JYWH4", "Mystery of The Four Compass Points", "abraham", "pdf", { season: "II", part: 8 }),
  w("11fG9AqaZWJNwkDQ9vswlEthFy1RqsnmI", "The Holy Tree of Mamre", "abraham", "pdf", { season: "II", part: 9 }),
  w("1melLxPegtCuhwkSpNA_60waDIlDDRWeN", "Creativity of The Word I", "abraham", "pdf", { season: "II", part: 11 }),
  w("1mXK6ZprMA-UVZQmxubluys6YtgTpnGy7", "Creativity Of The Word II", "abraham", "pdf", { season: "II", part: 12 }),
  w("1mozG1gXDaTR-Kqa469S4zIjO_8Dpt8AF", "Intelligence Of The Seed I", "abraham", "doc", { season: "II", part: 13 }),
  w("1mJaBkrbL_Iyz-cwdFMa2sHzSUAWgDm49", "Intelligence of the Seed II", "abraham", "doc", { season: "II", part: 14 }),
  w("1v_CBT8JjJu8t00FpzKjbksghtT3iLBh_", "Walk Before Me — The Room", "abraham", "pdf", { season: "II", part: 15 }),
  w("1vG7gn8MzFnH-crvg8EPq2cXQ6a0TgBeL", "Erkhomai — The Throne Room", "abraham", "pdf", { season: "II", part: 16 }),
  w("1vYZ1Ds4s951ZhBT3JA823q95PPM7a91z", "How To Ascend Into Heaven", "abraham", "pdf", { season: "II", part: 18 }),
  w("1vIsBiV-0VJwIv1-wDWnCHKG3oK1ikSjm", "The Mysteries of Angels — The Angelic Network", "abraham", "pdf", {
    season: "II",
    part: 19,
  }),
  w("1vaumgsTYNIXVfQt9rluBg2k19jkkejiB", "Moving Bodies — Season Special", "abraham", "pdf", {
    season: "II",
    part: 20,
  }),

  w("128BYYTlpHxBJpM6dSDoCr7fpv81GVrJe", "Mystery of Melchizedek · Part 1", "melchizedek", "pdf", { part: 1 }),
  w("10_MmQldZ9H-NEvxHbnLY9v_ZB6I1SLlQ", "Mystery of Melchizedek · Part 2", "melchizedek", "pdf", { part: 2 }),
  w("10u-82I7HX8gpp4pa_G0KyXrau8oMR9WE", "Mystery of Melchizedek · Part 3", "melchizedek", "pdf", { part: 3 }),
  w("11ag-vYWtkMuA_gwsObmqsafftajplkdI", "The Spirit Leak", "melchizedek", "pdf", { part: 4 }),
  w("10u4-Y2I5EZgw1ZheLTpxN4Prj5-QVIx1", "The Adventures of God I", "melchizedek", "pdf", { part: 5 }),
  w("11h4SxIeqxEm9IXOU5dtNlHFN_1tXuatq", "The Adventures of God II", "melchizedek", "pdf", { part: 6 }),
  w("1NttOJu-D3pZz7whvs1WYbQ1fmEHTc-TK", "The Forgotten Adam", "melchizedek", "pdf", { part: 7 }),
  w("116Gr-7ZhuRjkElzxk_TV2ZZJZWjeZTlG", "The Ekklisia", "melchizedek", "doc", { part: 8 }),
  w("113tP_hz4VZOeM07EzrcUdhUv4qs3ElfT", "The World Beneath Us", "melchizedek", "pdf", { part: 9 }),
  w("10lXE1EMWxoqPRcLC6bsirqfTblMyeT0w", "The World Beneath Us II", "melchizedek", "doc", { part: 10 }),
  w("11zeBFJGcKobIczH1dkuNioTFR6ntZC2z", "Welcome to The Kingdom of Righteousness", "melchizedek", "doc", { part: 11 }),
  w("11FWOjWTtWywyo-zXoYvTslMdmN6mf5Hc", "The Throne & Righteousness", "melchizedek", "doc", { part: 12 }),
  w("116SlZLNiDH23Kqv-VQTPmL1GuBA_iqbW", "The Corruption of the Earth", "melchizedek", "doc", { part: 13 }),
  w("1CtEWeU5V56URhlZaJ3vFxG88zmvYBisG", "The Dark Tales", "melchizedek", "pdf", { part: 14 }),
  w("1NRWOM_r8yoL2OXGA35mRIox4znTtCLmv", "Spirit Cities and Civilizations", "melchizedek", "doc", { part: 15 }),
  w("1NdWcY8tkR01ozgUIFxU_a4pwWi1NuNJL", "The Genesis of Priesthood", "melchizedek", "doc", { part: 16 }),
  w("1mHRnr1mOz_jcemqKPYE7OYgmcbKaK6QT", "The Ministry of The High Priest", "melchizedek", "pdf", { part: 17 }),

  w("13oS18ctz-fizhkUoWctZHVcksptRdtEO", "Heis Series · Part 1", "heis", "doc", { part: 1 }),
  w("13hFL1_lwcWuswLY_cKmhNfMbRN-lemx2", "Heis Series · Part 2", "heis", "doc", { part: 2 }),
  w("13uzb43K4FSGJsvYod1vWk4xcMAi1vzty", "Heis Series · Part 3", "heis", "doc", { part: 3 }),
  w("13lRaMDCeKLuzFSUYX45LF-fCCIr7xy-7", "Heis Series · Part 5", "heis", "doc", { part: 5 }),
  w("13fdaYG9qyHO1hQJN8FcAJ5zGgXwmWKsE", "Seed Of God I", "heis", "doc", { part: 6 }),
  w("13uw32OqWm_pwk4JH2efvnEkh4Xuy4S9I", "Seed Of God II", "heis", "doc", { part: 7 }),
  w("13v7OWTf83IZpJBOaZJH4oLYCHQT954M2", "Heis Series · Part 8", "heis", "doc", { part: 8 }),
  w("13keCvmGDz8lCoLa6pFU7sQ0UCnQxCF8p", "Heis Series · Part 9", "heis", "doc", { part: 9 }),

  w("12gIEik_AGYJSfbUxUq3No4YPFMZoq4vJ", "Aliens of Glory", "unmasking", "doc", { part: 1 }),
  w("135wieSK_1N4OoUNXy8TUddCuIhJcEz6d", "The Apocalypse I", "unmasking", "doc", { part: 2 }),
  w("13F1rixOVsNDdYdCQIN1wqaKhbYF30z1F", "The Apocalypse II", "unmasking", "doc", { part: 3 }),
  w("13J0nb9TJxbrqowrMmLa9em6SaxbK898_", "Dealing With The Flesh I", "unmasking", "doc", { part: 4 }),
  w("13BlYk7Xl8X-vlfRPQhpuutvuU5oCD59A", "Dealing With The Flesh II", "unmasking", "doc", { part: 5 }),
  w("12wtIQKQnc466U6RS1WX48Vtt5GOUFzIi", "Dealing With The Flesh III", "unmasking", "doc", { part: 6 }),
  w("12yEvmAZSjnO7dmYRilS8YKI__l9zxc4h", "How It All Went Wrong I", "unmasking", "doc", { part: 7 }),
  w("13LIcerjFmWMwlBtxgfFurltqEO2wm2bU", "How It All Went Wrong II", "unmasking", "doc", { part: 8 }),
  w("13LZnRIYCtxA5KXtqxaxg7FYFiv_NDACf", "My Own World I", "unmasking", "doc", { part: 9 }),
  w("1343nFZiJjuij8alaeCdk-ArFgPZl4-Tk", "My Own World II", "unmasking", "doc", { part: 10 }),
  w("13S4R4KpYRdF2mR1b-3tnmIACw-7tcvzG", "We Have Come Unto Mt Zion", "unmasking", "doc", { part: 11 }),
  w("130EuirI-RbdCCs4URTvrhdK7-BCSaHJX", "You Were Delivered I", "unmasking", "doc", { part: 12 }),

  w("12Gb9_07wFPYR3NtkrXiPr5_GHd4qmKTw", "Mind-Heart-Word I", "word", "doc", { part: 1 }),
  w("12Lxm5_PktrJZDkiIoiS32olt99SM88Mr", "Mind-Heart-Word II", "word", "doc", { part: 2 }),
  w("12B9easieRrYxPba4YTdI-TgsNVfo6HHg", "Mind-Heart-Word III", "word", "doc", { part: 3 }),
  w("12F1NQKo_7xWRHgWZKduhbd-3p-ydfvQC", "Standing With The Word", "word", "doc", { part: 4 }),
  w("12QpOd6K10YttuKC8pdceI_5vPXVnQf3E", "Sure Word of Prophecy", "word", "doc", { part: 5 }),
  w("12GlnlRIK1y8MuaL-4QykW5fv4QNQcBwY", "Eating With The Word", "word", "doc", { part: 6 }),
  w("12HfGQUX3E49OGXuNXBFmVOSoCHeEivF5", "Hiding The Word", "word", "doc", { part: 7 }),
  w("12JRBDf-TZ2n1-w7O36B_iZ2lbmUYXa_-", "Sleeping On The Word", "word", "doc", { part: 8 }),

  w("12TaDqC7hr5QN0ENOgzzOmRrkNfyeWm9H", "Road to Meditation I", "meditation", "doc", { part: 1 }),
  w("12UQjf9k2u23wAgWjs0Ef6nLaXcg2Wexz", "Road to Meditation II", "meditation", "pdf", { part: 2 }),
  w("12VsZtkt3nSIBGwxfisOii6RWkO3GG5Sb", "The Course of Meditation", "meditation", "pdf", { part: 3 }),

  w("1RTRmu2gMP625kEXSrTV7Oc68YhkziNr1", "Church Witchcraft · Issue #1", "comics", "pdf", {
    featured: true,
    part: 1,
  }),
  w("1pCFNkt3I1DfGhnm6sgbIfxXhmHyTTWDd", "Characters · Terms and Conditions", "comics", "pdf", { part: 0 }),

  w("13mBbjutIfVNr-0USCrUsmbNT8ENc2526", "Bible Secrets Defined", "others", "doc", { featured: true, part: 1 }),
  w("142da-fRb3ahxxd43Y-GGyXYIk9dwUn4q", "Ascension", "others", "doc", { part: 2 }),
  w("149fyvQSErCoi3gupHgczoNcGT3bInalx", "Communion", "others", "pdf", { part: 3 }),
  w("14HTUIl07wJ2zyMD1gxZXr_SjKbzF2Cwx", "Gravitation — Kudakwashe Mukewa", "others", "doc", { part: 4 }),
  w("14JjQL4OGPpvT--4NhjhslBxB9BoOm9_P", "Leviticus", "others", "doc", { part: 5 }),
  w("14DvOEbWcaP_dTsf27zy42qnIt8BwNXWz", "Mind Of Christ — Trust Chikwizo", "others", "doc", { part: 6 }),
  w("144lKzdfwjSrIHzX6Ox3cW5ddo_nes9Ft", "Spirit Chats", "others", "doc", { part: 7 }),
  w("143tVS8s7WKFRkgPbpRBn2j6pR7_7-LGG", "Sword Of The Spirit", "others", "doc", { part: 8 }),
];

export const seriesById = Object.fromEntries(series.map((s) => [s.id, s])) as Record<string, Series>;
export const workById = Object.fromEntries(works.map((x) => [x.id, x])) as Record<string, Work>;

export function worksInSeries(seriesId: string): Work[] {
  return works
    .filter((x) => x.seriesId === seriesId)
    .sort((a, b) => {
      const sa = a.season ?? "";
      const sb = b.season ?? "";
      if (sa !== sb) {
        const order = ["pre", "I", "II", ""];
        return order.indexOf(sa) - order.indexOf(sb);
      }
      return (a.part ?? 0) - (b.part ?? 0);
    });
}

export function siblings(work: Work): { prev?: Work; next?: Work } {
  const list = worksInSeries(work.seriesId);
  const i = list.findIndex((x) => x.id === work.id);
  return { prev: list[i - 1], next: list[i + 1] };
}

export function previewUrl(work: Work): string {
  return `https://drive.google.com/file/d/${work.driveId}/preview`;
}

export function downloadUrl(work: Work): string {
  return `https://drive.google.com/uc?id=${work.driveId}&export=download`;
}

export function searchWorks(q: string): Work[] {
  const s = q.trim().toLowerCase();
  if (!s) return [];
  return works.filter((w) => {
    const ser = seriesById[w.seriesId];
    return (
      w.title.toLowerCase().includes(s) ||
      ser?.title.toLowerCase().includes(s) ||
      ser?.tagline.toLowerCase().includes(s) ||
      (w.blurb ?? "").toLowerCase().includes(s)
    );
  });
}
