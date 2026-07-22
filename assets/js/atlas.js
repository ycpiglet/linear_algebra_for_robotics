(() => {
  'use strict';

  const SITE_ROOT = window.__ROBOTICS_MATH_ATLAS_ROOT__ || new URL('./', document.baseURI).href;
  const MANIFEST_URL = new URL('platform/generated/concept-manifest.json', SITE_ROOT).href;
  const STORAGE_KEY = 'robotics-math-atlas.progress.v1';
  const LEGACY_REPOSITORY_SLUG = 'linear_algebra_for_robotics';
  const CANONICAL_REPOSITORY_SLUG = 'robotics-math-atlas';
  const SAVED_PATH_MIGRATION = 'savedPathsV1';
  const DEPTHS = [
    { id: 'intuition', label: '직관', rank: 0 },
    { id: 'application', label: '계산·적용', rank: 1 },
    { id: 'derivation', label: '유도', rank: 2 },
    { id: 'proof', label: '증명·가정', rank: 3 },
  ];
  const METADATA_DEPTH_ORDER = [
    'intuition',
    'application',
    'analysis',
    'implementation',
    'derivation',
    'proof',
    'teaching',
  ];
  const METADATA_DEPTH_LABELS = {
    intuition: '직관',
    application: '계산·적용',
    analysis: '분석',
    implementation: '구현',
    derivation: '유도',
    proof: '증명',
    teaching: '가르치기',
  };
  const UI_DEPTH_LIMIT = {
    intuition: 0,
    application: 3,
    derivation: 4,
    proof: 5,
  };
  const PREREQUISITE_CATEGORIES = [
    {
      id: 'required',
      label: '필수',
      description: '이 깊이를 읽기 전에 준비해야 하는 개념',
    },
    {
      id: 'helpful',
      label: '도움',
      description: '없어도 시작할 수 있지만 막힐 때 먼저 복습할 개념',
    },
    {
      id: 'not_required',
      label: '필요 없음',
      description: '이 깊이에서는 미리 공부하지 않아도 되는 개념',
    },
  ];
  const PREREQUISITE_CATEGORY_PRIORITY = new Map(
    PREREQUISITE_CATEGORIES.map((category, index) => [category.id, index]),
  );
  const MASTERY = [
    '처음 봄',
    '직관 설명 가능',
    '계산·적용 가능',
    '유도 가능',
    '증명·가정 설명 가능',
    '가르칠 수 있음',
  ];
  const DOMAIN_LABELS = {
    'linear-algebra': '선형대수',
    linear_algebra: '선형대수',
    probability: '확률·통계',
    estimation: '상태추정',
    control: '제어',
    signals: '신호·시스템',
    systems: '신호·시스템',
    optimization: '최적화',
    linalg: '선형대수',
    'monte-carlo': '몬테카를로(Monte Carlo)',
    monte_carlo: '몬테카를로(Monte Carlo)',
    foundations: '기초 수학',
    statistics: '통계·추정',
    robotics: '로봇공학',
    mechanics: '역학·기구학',
    sensors: '센서공학',
    ai: '인공지능·학습',
  };
  const PLANNED_CONCEPT_LABELS = {
    'control.anti_windup': '적분 포화 방지(anti-windup)',
    'control.feedforward': '앞먹임 제어(feedforward control)',
    'control.frequency_response': '주파수응답(frequency response)',
    'control.state_feedback': '상태피드백(state feedback)',
    'estimation.extended_kalman_filter': '확장 칼만 필터(Extended Kalman Filter, EKF)',
    'estimation.innovation_orthogonality': '혁신 직교성(innovation orthogonality)',
    'estimation.particle_filter': '입자 필터(particle filter)',
    'estimation.rts_smoother': '라우흐–퉁–스트리벨 평활기(RTS smoother)',
    'estimation.square_root_filter': '제곱근 필터(square-root filter)',
    'linalg.inner_product': '내적(inner product)',
    'linalg.vector_space': '벡터공간(vector space)',
    'linalg.weighted_least_squares': '가중최소제곱(weighted least squares)',
    'optimization.absolute_deviation': '절대편차최소화(least absolute deviations)',
    'optimization.nonlinear_least_squares': '비선형 최소제곱(nonlinear least squares)',
    'probability.stochastic_process': '확률과정(stochastic process)',
    'robot.calibration': '로봇 보정(robot calibration)',
    'robot.dynamics': '로봇 동역학(robot dynamics)',
    'robot.force_control': '힘 제어(force control)',
    'robot.forward_kinematics': '순기구학(forward kinematics)',
    'robot.impedance_control': '임피던스 제어(impedance control)',
    'robot.inverse_kinematics': '역기구학(inverse kinematics)',
    'robot.joint_control': '관절 제어(joint control)',
    'robot.localization': '위치추정(localization)',
    'robot.manipulability': '조작성(manipulability)',
    'robot.mobile_velocity_control': '이동로봇 속도제어(mobile velocity control)',
    'robot.operational_space_control': '작업공간 제어(operational-space control)',
    'robot.sensor_fusion': '센서 융합(sensor fusion)',
    'robot.state_estimation': '로봇 상태추정(robot state estimation)',
    'signals.low_pass_filter': '저역통과필터(low-pass filter)',
    'statistics.fisher_information': '피셔 정보(Fisher information)',
    'statistics.generalized_linear_model': '일반화선형모형(generalized linear model)',
    'statistics.linear_measurement': '선형 측정모형(linear measurement model)',
    'statistics.maximum_a_posteriori': '최대사후확률추정(Maximum A Posteriori, MAP)',
  };

  const conceptDisplayName = (id) => PLANNED_CONCEPT_LABELS[id] || id;

  const escapeHtml = (value) => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const arrayOf = (value) => {
    if (Array.isArray(value)) return value;
    if (value === undefined || value === null || value === '') return [];
    return [value];
  };

  const itemId = (value) => {
    if (typeof value === 'string') return value;
    return value?.id || value?.concept || value?.target || value?.proof || '';
  };

  const itemDepth = (value) => {
    if (typeof value === 'string') return '직관';
    const depth = value?.depth || value?.minimum_depth || value?.level || 'intuition';
    return METADATA_DEPTH_LABELS[depth] || String(depth);
  };

  const flattenPrerequisites = (value) => {
    if (!value) return [];
    if (Array.isArray(value)) return value;
    if (typeof value !== 'object') return [value];
    const result = [];
    Object.entries(value).forEach(([depth, group]) => {
      if (Array.isArray(group)) {
        group.forEach((entry) => result.push({
          ...(typeof entry === 'string' ? { concept: entry } : entry),
          depth,
          category: 'required',
        }));
        return;
      }
      if (!group || typeof group !== 'object') return;
      PREREQUISITE_CATEGORIES.forEach(({ id: category }) => {
        const rawEntries = category === 'not_required'
          ? [...arrayOf(group.not_required), ...arrayOf(group['not-required'])]
          : arrayOf(group[category]);
        rawEntries.forEach((entry) => result.push({
          ...(typeof entry === 'string' ? { concept: entry } : entry),
          depth,
          category,
        }));
      });
    });
    const unique = new Map();
    result.forEach((entry) => {
      const id = itemId(entry);
      const key = `${id}:${entry.depth}:${entry.category}`;
      if (id && !unique.has(key)) unique.set(key, entry);
    });
    return [...unique.values()];
  };

  const prerequisitesAtDepth = (concept, selectedDepth) => {
    const limit = UI_DEPTH_LIMIT[selectedDepth] ?? UI_DEPTH_LIMIT.proof;
    const eligible = concept.prerequisites.filter((entry) => {
      const rank = METADATA_DEPTH_ORDER.indexOf(entry.depth || 'intuition');
      return rank >= 0 && rank <= limit;
    });
    const selected = new Map();
    eligible.forEach((entry) => {
      const id = itemId(entry);
      if (!id) return;
      const previous = selected.get(id);
      const rank = METADATA_DEPTH_ORDER.indexOf(entry.depth || 'intuition');
      const previousRank = previous
        ? METADATA_DEPTH_ORDER.indexOf(previous.depth || 'intuition')
        : -1;
      const priority = PREREQUISITE_CATEGORY_PRIORITY.get(entry.category) ?? 99;
      const previousPriority = previous
        ? (PREREQUISITE_CATEGORY_PRIORITY.get(previous.category) ?? 99)
        : 99;
      const replacesPrevious = !previous
        || rank > previousRank
        || (rank === previousRank && priority < previousPriority);
      if (replacesPrevious) selected.set(id, entry);
    });
    return [...selected.values()].sort((left, right) => {
      const leftPriority = PREREQUISITE_CATEGORY_PRIORITY.get(left.category) ?? 99;
      const rightPriority = PREREQUISITE_CATEGORY_PRIORITY.get(right.category) ?? 99;
      if (leftPriority !== rightPriority) return leftPriority - rightPriority;
      return itemId(left).localeCompare(itemId(right));
    });
  };

  const formatReadingTime = (value) => {
    if (typeof value === 'number' && Number.isFinite(value) && value > 0) return `${value}분`;
    if (typeof value !== 'string') return '';
    return value.trim();
  };

  const readingTimeEntries = (value) => {
    if (value === undefined || value === null || value === '') return [];
    if (typeof value !== 'object' || Array.isArray(value)) {
      const duration = formatReadingTime(value);
      return duration ? [{ id: 'full', label: '전체', duration }] : [];
    }
    return [
      { id: 'quick', label: '빠른', duration: formatReadingTime(value.quick) },
      { id: 'core', label: '핵심', duration: formatReadingTime(value.core) },
      { id: 'full', label: '전체', duration: formatReadingTime(value.full) },
    ].filter((entry) => entry.duration);
  };

  const makeReadingTime = (value) => {
    const entries = readingTimeEntries(value);
    if (!entries.length) return '';
    return `
      <div class="concept-toolbar__reading-time" role="group" aria-label="예상 읽기 시간">
        <p class="concept-toolbar__reading-time-title" aria-hidden="true">예상 읽기 시간</p>
        <ul class="concept-toolbar__reading-time-list" role="list">
          ${entries.map((entry) => `
            <li aria-label="${escapeHtml(entry.label)} 읽기 예상 시간 ${escapeHtml(entry.duration)}">
              <span>${escapeHtml(entry.label)}</span>
              <strong>${escapeHtml(entry.duration)}</strong>
            </li>
          `).join('')}
        </ul>
      </div>
    `;
  };

  const flattenRelations = (value) => {
    if (!value) return [];
    if (Array.isArray(value)) return value;
    if (typeof value !== 'object') return [value];
    return Object.entries(value).flatMap(([relation, targets]) => arrayOf(targets).map((target) => ({
      ...(typeof target === 'string' ? { concept: target } : target),
      relation,
    })));
  };

  const flattenBacklinks = (value) => {
    if (!value) return [];
    if (Array.isArray(value)) return value;
    if (typeof value !== 'object') return [value];
    return Object.entries(value).flatMap(([relation, targets]) => arrayOf(targets).map((target) => ({
      ...(typeof target === 'string' ? { concept: target } : target),
      relation,
    })));
  };

  const localUrl = (path) => {
    if (!path) return '#';
    if (/^(https?:|mailto:|#)/.test(path)) return path;
    return new URL(String(path).replace(/^\//, ''), SITE_ROOT).href;
  };

  const projectRootUrl = (siteRoot = SITE_ROOT, origin = window.location.origin) => {
    const root = new URL(siteRoot, `${origin}/`);
    const parts = root.pathname.split('/').filter(Boolean);
    const repositoryIndex = parts.findIndex((part) => (
      part === LEGACY_REPOSITORY_SLUG || part === CANONICAL_REPOSITORY_SLUG
    ));
    if (root.origin !== origin || repositoryIndex < 0) return root;
    root.pathname = `/${parts.slice(0, repositoryIndex + 1).join('/')}/`;
    root.search = '';
    root.hash = '';
    return root;
  };

  const siteRelativePath = (value, siteRoot = SITE_ROOT, origin = window.location.origin) => {
    if (typeof value !== 'string' || !value) return value;
    let candidate;
    let projectRoot;
    try {
      projectRoot = projectRootUrl(siteRoot, origin);
      candidate = new URL(value, projectRoot);
    } catch (_error) {
      return value;
    }
    if (!['http:', 'https:'].includes(candidate.protocol) || candidate.origin !== origin) {
      return value;
    }

    const parts = candidate.pathname.split('/').filter(Boolean);
    if (parts[0] === LEGACY_REPOSITORY_SLUG
      || parts[0] === CANONICAL_REPOSITORY_SLUG) {
      return `${parts.slice(1).join('/')}${candidate.search}${candidate.hash}`;
    }
    const rootPath = projectRoot.pathname.replace(/\/+$/, '/');
    if (candidate.pathname.startsWith(rootPath)) {
      return `${candidate.pathname.slice(rootPath.length)}${candidate.search}${candidate.hash}`;
    }
    return value;
  };

  const safeSavedUrl = (value) => {
    try {
      const projectRoot = projectRootUrl();
      const relative = siteRelativePath(value);
      const url = new URL(String(relative || ''), projectRoot);
      if (!['http:', 'https:'].includes(url.protocol)
        || url.origin !== window.location.origin
        || !url.pathname.startsWith(projectRoot.pathname)) return '#';
      return url.href;
    } catch (_error) {
      return '#';
    }
  };

  const returnUrl = (target) => {
    const url = new URL(localUrl(target));
    url.searchParams.set('return', window.location.href);
    return url.href;
  };

  const migrateSavedMap = (entries, normalize) => {
    const migrated = {};
    const priorities = {};
    let changed = false;
    Object.entries(entries || {}).forEach(([key, rawEntry]) => {
      const migratedKey = normalize(key);
      const migratedEntry = rawEntry && typeof rawEntry === 'object' && !Array.isArray(rawEntry)
        ? { ...rawEntry, url: normalize(rawEntry.url) }
        : rawEntry;
      changed ||= migratedKey !== key
        || migratedEntry?.url !== rawEntry?.url;
      const previous = migrated[migratedKey];
      const timestamp = String(migratedEntry?.updatedAt || '');
      const previousTimestamp = String(previous?.updatedAt || '');
      const priority = migratedKey === key ? 1 : 0;
      if (previous === undefined || timestamp > previousTimestamp
        || (timestamp === previousTimestamp && priority > (priorities[migratedKey] || 0))) {
        migrated[migratedKey] = migratedEntry;
        priorities[migratedKey] = priority;
      }
    });
    return { entries: migrated, changed };
  };

  const migrateProgressPaths = (
    state,
    siteRoot = SITE_ROOT,
    origin = window.location.origin,
  ) => {
    const normalize = (value) => siteRelativePath(value, siteRoot, origin);
    let changed = false;
    ['bookmarks', 'favorites', 'lastRead'].forEach((field) => {
      const result = migrateSavedMap(state[field], normalize);
      state[field] = result.entries;
      changed ||= result.changed;
    });
    state.migrations = state.migrations && typeof state.migrations === 'object'
      ? state.migrations
      : {};
    if (state.migrations[SAVED_PATH_MIGRATION] !== true) {
      state.migrations[SAVED_PATH_MIGRATION] = true;
      changed = true;
    }
    return changed;
  };

  const currentPageKey = () => siteRelativePath(window.location.href);

  const loadProgress = () => {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      return {
        version: 1,
        concepts: parsed.concepts && typeof parsed.concepts === 'object' ? parsed.concepts : {},
        depth: parsed.depth && typeof parsed.depth === 'object' ? parsed.depth : {},
        bookmarks: parsed.bookmarks && typeof parsed.bookmarks === 'object' ? parsed.bookmarks : {},
        favorites: parsed.favorites && typeof parsed.favorites === 'object' ? parsed.favorites : {},
        lastRead: parsed.lastRead && typeof parsed.lastRead === 'object' ? parsed.lastRead : {},
        migrations: parsed.migrations && typeof parsed.migrations === 'object'
          ? parsed.migrations
          : {},
        updatedAt: parsed.updatedAt || null,
      };
    } catch (_error) {
      return {
        version: 1,
        concepts: {},
        depth: {},
        bookmarks: {},
        favorites: {},
        lastRead: {},
        migrations: {},
        updatedAt: null,
      };
    }
  };

  const progress = loadProgress();
  const progressPathsMigrated = migrateProgressPaths(progress);

  const persistProgress = () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(progress));
      return true;
    } catch (_error) {
      document.documentElement.dataset.atlasStorage = 'unavailable';
      return false;
    }
  };

  // The old and new project Pages sites share the github.io origin. Persist
  // prefix-neutral paths before any reader tool consumes the maps.
  if (progressPathsMigrated) persistProgress();

  const saveProgress = () => {
    progress.updatedAt = new Date().toISOString();
    persistProgress();
    document.dispatchEvent(new CustomEvent('atlas:progress'));
  };

  const normalizeConcept = (concept) => ({
    ...concept,
    id: concept.id || concept.slug || '',
    title: concept.title || concept.name || concept.id || '제목 없음',
    domain: concept.domain || 'foundations',
    aliases: arrayOf(concept.aliases),
    prerequisites: flattenPrerequisites(concept.prerequisites),
    relations: flattenRelations(concept.relations || concept.related),
    backlinks: flattenBacklinks(concept.backlinks),
    url: concept.url || concept.href || concept.output || '#',
    summary: concept.summary || concept.one_line || concept.description || '',
  });

  const conceptIndex = (manifest) => {
    const concepts = arrayOf(manifest.concepts).map(normalizeConcept);
    const byId = new Map(concepts.map((concept) => [concept.id, concept]));
    return { concepts, byId };
  };

  const conceptLink = (concept, options = {}) => {
    if (!concept) return '<span>알 수 없는 개념</span>';
    const href = options.withReturn ? returnUrl(concept.url) : localUrl(concept.url);
    return `<a href="${escapeHtml(href)}">${escapeHtml(concept.title)}</a>`;
  };

  const injectReturnBanner = () => {
    const rawReturn = new URLSearchParams(window.location.search).get('return');
    if (!rawReturn) return;

    let destination;
    try {
      destination = new URL(rawReturn, window.location.href);
      if (destination.origin !== window.location.origin) return;
    } catch (_error) {
      return;
    }

    const main = document.querySelector('main.content, main');
    if (!main) return;
    const banner = document.createElement('aside');
    banner.className = 'return-banner';
    banner.setAttribute('aria-label', '원래 학습 위치로 돌아가기');
    banner.innerHTML = `
      <span>선수개념 복습 중입니다. 준비되면 원래 읽던 곳으로 돌아가세요.</span>
      <a class="atlas-button atlas-button--primary" href="${escapeHtml(destination.href)}">돌아가기</a>
    `;
    main.prepend(banner);
  };

  const renderDepthMarkers = () => {
    const labels = {
      intuition: '직관',
      application: '적용',
      derivation: '유도',
      proof: '증명',
    };
    Object.entries(labels).forEach(([depth, label]) => {
      document.querySelectorAll(`.depth-${depth}`).forEach((section) => {
        if (section.querySelector('.depth-marker')) return;
        const marker = document.createElement('span');
        marker.className = 'depth-marker';
        marker.textContent = label;
        // 홀로 떠 있는 칩 대신 절 제목 옆의 배지로 붙인다 — 제목이 없을 때만 앞에 둔다.
        const heading = section.querySelector('h2, h3, h4');
        if (heading) {
          marker.classList.add('depth-marker--heading');
          heading.appendChild(marker);
        } else {
          section.prepend(marker);
        }
      });
    });
  };

  const applyDepth = (conceptId, selectedDepth, toolbar) => {
    const selectedRank = DEPTHS.find((entry) => entry.id === selectedDepth)?.rank ?? 3;
    DEPTHS.forEach(({ id, rank }) => {
      document.querySelectorAll(`.depth-${id}`).forEach((section) => {
        section.classList.toggle('depth-hidden', rank > selectedRank);
        section.setAttribute('aria-hidden', rank > selectedRank ? 'true' : 'false');
      });
    });
    toolbar.querySelectorAll('.depth-tab').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.depth === selectedDepth));
    });
    progress.depth[conceptId] = selectedDepth;
    saveProgress();
    document.dispatchEvent(new CustomEvent('atlas:depth', {
      detail: { conceptId, selectedDepth },
    }));
  };

  const makePrerequisites = (concept, byId, selectedDepth) => {
    const entries = prerequisitesAtDepth(concept, selectedDepth);
    if (!entries.length) {
      return '<p>이 깊이에는 따로 준비할 선수개념이 없습니다.</p>';
    }
    const groups = PREREQUISITE_CATEGORIES
      .map((category) => ({
        ...category,
        entries: entries.filter((entry) => entry.category === category.id),
      }))
      .filter((group) => group.entries.length);
    return `
      <div class="prerequisite-groups">
        ${groups.map((group) => `
          <section class="prerequisite-group prerequisite-group--${escapeHtml(group.id.replace('_', '-'))}"
            aria-label="${escapeHtml(group.label)} 선수지식 ${group.entries.length}개">
            <div class="prerequisite-group__heading">
              <h3>${escapeHtml(group.label)} <span>${group.entries.length}개</span></h3>
              <p>${escapeHtml(group.description)}</p>
            </div>
            <ul class="prerequisite-list">
              ${group.entries.map((entry) => {
                const id = itemId(entry);
                const prerequisite = byId.get(id) || {
                  id,
                  title: conceptDisplayName(id),
                  url: '#',
                };
                const checked = Number(progress.concepts[id] || 0) >= 1;
                const marker = group.id === 'not_required'
                  ? '<span class="prerequisite-item__marker" aria-hidden="true">—</span>'
                  : `<input type="checkbox" data-prerequisite-id="${escapeHtml(id)}"
                      aria-label="${escapeHtml(prerequisite.title)}, ${escapeHtml(group.label)} 선수지식 준비됨" ${checked ? 'checked' : ''}>`;
                return `
                  <li class="prerequisite-item" data-prerequisite-category="${escapeHtml(group.id)}">
                    ${marker}
                    <span>
                      ${conceptLink(prerequisite, { withReturn: prerequisite.url !== '#' })}
                      ${entry.reason ? `<small class="prerequisite-item__reason">${escapeHtml(entry.reason)}</small>` : ''}
                    </span>
                    <span class="prerequisite-item__depth">${escapeHtml(group.label)} · ${escapeHtml(itemDepth(entry))}</span>
                  </li>
                `;
              }).join('')}
            </ul>
          </section>
        `).join('')}
      </div>
    `;
  };

  const prerequisiteSummary = (entries) => {
    const groups = PREREQUISITE_CATEGORIES
      .map((category) => ({
        label: category.label,
        count: entries.filter((entry) => entry.category === category.id).length,
      }))
      .filter((group) => group.count);
    if (!groups.length) return '선수개념 체크리스트 · 별도 준비 없음';
    return `선수개념 체크리스트 · ${groups.map((group) => `${group.label} ${group.count}`).join(' · ')}`;
  };

  const makeBacklinks = (concept, byId) => {
    if (!concept.backlinks.length && !concept.relations.length) return '';
    const candidates = [...concept.relations, ...concept.backlinks];
    const uniqueEntries = candidates.filter((entry, index) => {
      const id = itemId(entry);
      return id && candidates.findIndex((candidate) => itemId(candidate) === id) === index;
    });
    const entries = uniqueEntries.filter((entry) => byId.has(itemId(entry)) || entry.url);
    const planned = uniqueEntries.filter((entry) => !byId.has(itemId(entry)) && !entry.url);
    return `
      <details class="backlink-panel">
        <summary>연결된 페이지 ${entries.length}개${planned.length ? ` · 향후 확장 ${planned.length}개` : ''}</summary>
        ${entries.length ? `
          <ul class="relation-list">
            ${entries.map((entry) => {
              const id = itemId(entry);
              const reference = byId.get(id) || {
                id,
                title: entry.title || id,
                url: entry.url,
              };
              return `<li>${conceptLink(reference)}</li>`;
            }).join('')}
          </ul>
        ` : ''}
        ${planned.length ? `
          <div class="chip-row" aria-label="아직 작성되지 않은 확장 개념">
            ${planned.map((entry) => {
              const id = itemId(entry);
              return `<a class="chip chip--planned" href="${escapeHtml(localUrl('future-scope.html'))}" title="향후 확장 노드 목록에서 보기">${escapeHtml(conceptDisplayName(id))} · 예정</a>`;
            }).join('')}
          </div>
        ` : ''}
      </details>
    `;
  };

  const renderConceptToolbar = (manifest) => {
    const meta = document.querySelector('#concept-meta[data-concept-id]');
    if (!meta) return;
    const { concepts, byId } = conceptIndex(manifest);
    const conceptId = meta.dataset.conceptId;
    const concept = byId.get(conceptId)
      || concepts.find((entry) => entry.id === conceptId)
      || normalizeConcept({ id: conceptId, title: document.title, domain: meta.dataset.conceptDomain });

    const toolbar = document.createElement('section');
    toolbar.className = 'concept-toolbar';
    toolbar.setAttribute('aria-label', `${concept.title} 학습 도구`);
    const currentMastery = Math.max(0, Math.min(5, Number(progress.concepts[conceptId] || 0)));
    const currentDepth = progress.depth[conceptId] || 'application';
    const showPrerequisites = window.matchMedia('(min-width: 58rem)').matches;
    toolbar.innerHTML = `
      <div class="concept-toolbar__top">
        <div>
          <h2 class="concept-toolbar__title">이 페이지의 학습 지도</h2>
          <div class="chip-row">
            <span class="chip chip--domain">${escapeHtml(DOMAIN_LABELS[concept.domain] || concept.domain)}</span>
            ${concept.importance ? `<span class="chip chip--importance" title="뒤의 개념과 실무에서 다시 쓰이는 정도">중요도 ${escapeHtml(concept.importance)}/5</span>` : ''}
            ${concept.difficulty ? `<span class="chip chip--difficulty" title="이 장을 유도까지 읽을 때의 사고량">난이도 ${escapeHtml(concept.difficulty)}/5</span>` : ''}
            ${concept.practice_frequency ? `<span class="chip chip--practice" title="공개 구현·문서·로그에서 직접 만나는 정도">실무 빈도 ${escapeHtml(concept.practice_frequency)}/5</span>` : ''}
            ${arrayOf(concept.application_areas).slice(0, 5).map((area) => `<span class="chip chip--application" title="대표 쓰임">${escapeHtml(area)}</span>`).join('')}
            ${concept.aliases.slice(0, 4).map((alias) => `<span class="chip chip--alias" title="다른 표기">${escapeHtml(alias)}</span>`).join('')}
          </div>
        </div>
        <label class="atlas-field">
          <span>나의 숙달 상태</span>
          <select class="mastery-select" aria-label="숙달 상태">
            ${MASTERY.map((label, rank) => `<option value="${rank}" ${rank === currentMastery ? 'selected' : ''}>${escapeHtml(label)}</option>`).join('')}
          </select>
        </label>
      </div>
      ${concept.summary ? `<p>${escapeHtml(concept.summary)}</p>` : ''}
      ${concept.importance_note ? `<p class="concept-toolbar__importance"><strong>왜 중요한가:</strong> ${escapeHtml(concept.importance_note)}</p>` : ''}
      ${concept.practice_frequency_note ? `<p class="concept-toolbar__importance"><strong>실무 빈도 근거:</strong> ${escapeHtml(concept.practice_frequency_note)}</p>` : ''}
      ${makeReadingTime(concept.reading_time)}
      <div>
        <p class="concept-toolbar__title">이번에 볼 깊이</p>
        <div class="depth-tabs" role="group" aria-label="본문 깊이 선택">
          ${DEPTHS.map(({ id, label }) => `<button type="button" class="depth-tab" data-depth="${id}" aria-pressed="${id === currentDepth}">${label}까지</button>`).join('')}
        </div>
      </div>
      <details class="prerequisite-panel" ${showPrerequisites ? 'open' : ''}>
        <summary data-prerequisite-summary>선수개념 체크리스트</summary>
        <div data-prerequisite-body></div>
      </details>
      ${makeBacklinks(concept, byId)}
    `;

    const conceptHero = document.querySelector('#quarto-document-content > .concept-hero, .concept-hero');
    const titleBlock = document.querySelector('#title-block-header');
    if (conceptHero) conceptHero.insertAdjacentElement('afterend', toolbar);
    else if (titleBlock) titleBlock.insertAdjacentElement('afterend', toolbar);
    else meta.insertAdjacentElement('afterend', toolbar);

    toolbar.querySelector('.mastery-select')?.addEventListener('change', (event) => {
      progress.concepts[conceptId] = Number(event.target.value);
      saveProgress();
    });
    const refreshPrerequisites = (selectedDepth) => {
      const entries = prerequisitesAtDepth(concept, selectedDepth);
      const body = toolbar.querySelector('[data-prerequisite-body]');
      const summary = toolbar.querySelector('[data-prerequisite-summary]');
      body.innerHTML = makePrerequisites(concept, byId, selectedDepth);
      summary.textContent = prerequisiteSummary(entries);
      body.querySelectorAll('[data-prerequisite-id]').forEach((checkbox) => {
        checkbox.addEventListener('change', () => {
          const id = checkbox.dataset.prerequisiteId;
          const prior = Number(progress.concepts[id] || 0);
          progress.concepts[id] = checkbox.checked ? Math.max(prior, 1) : 0;
          saveProgress();
        });
      });
    };
    toolbar.querySelectorAll('.depth-tab').forEach((button) => {
      button.addEventListener('click', () => {
        applyDepth(conceptId, button.dataset.depth, toolbar);
        refreshPrerequisites(button.dataset.depth);
      });
    });

    renderDepthMarkers();
    refreshPrerequisites(currentDepth);
    applyDepth(conceptId, currentDepth, toolbar);
  };

  const graphEdges = (manifest, nodes, mode) => {
    const nodeIds = new Set(nodes.map((node) => node.id));
    const fromManifest = arrayOf(manifest.graph?.edges)
      .filter((edge) => edge.resolved !== false
        && edge.category !== 'not_required'
        && (mode !== 'concept' || ['prerequisite', 'relation'].includes(edge.type)))
      .map((edge) => ({
        source: edge.source || edge.from,
        target: edge.target || edge.to,
        type: edge.type || edge.relation || 'related',
        category: edge.category,
        depth: edge.depth,
        relation: edge.relation,
      }))
      .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target));
    if (fromManifest.length && mode !== 'proof') return fromManifest;

    return nodes.flatMap((node) => {
      const dependencies = mode === 'proof'
        ? arrayOf(node.dependencies || node.prerequisites)
        : arrayOf(node.prerequisites);
      return dependencies
        .filter((entry) => nodeIds.has(itemId(entry)))
        .map((entry) => ({
          source: itemId(entry),
          target: node.id,
          type: 'prerequisite',
          category: entry.category || 'required',
          depth: entry.depth || 'intuition',
        }));
    });
  };

  const radialPositions = (nodes, width, height) => {
    const centerX = width / 2;
    const centerY = height / 2;
    const rings = [];
    const ringSize = 12;
    nodes.forEach((node, index) => {
      const ring = Math.floor(index / ringSize);
      if (!rings[ring]) rings[ring] = [];
      rings[ring].push(node);
    });
    const result = new Map();
    rings.forEach((ringNodes, ring) => {
      const radius = ring === 0 ? Math.min(width, height) * 0.27 : Math.min(width, height) * (0.39 + ring * 0.11);
      ringNodes.forEach((node, index) => {
        const angle = -Math.PI / 2 + (2 * Math.PI * index) / ringNodes.length + ring * 0.16;
        result.set(node.id, {
          x: centerX + radius * Math.cos(angle),
          y: centerY + radius * Math.sin(angle),
        });
      });
    });
    return result;
  };

  const renderGraph = (container, listContainer, nodes, edges, options = {}) => {
    if (!container) return;
    if (!nodes.length) {
      container.innerHTML = '<div class="atlas-graph__empty">조건에 맞는 노드가 없습니다.</div>';
      if (listContainer) listContainer.innerHTML = '';
      return;
    }

    const width = Math.max(760, Math.min(1260, nodes.length * 82));
    const height = 510;
    const positions = radialPositions(nodes, width, height);
    const nodeById = new Map(nodes.map((node) => [node.id, node]));
    const clippedEdges = edges.filter((edge) => positions.has(edge.source) && positions.has(edge.target));
    const shorten = (value, length = 18) => value.length > length ? `${value.slice(0, length - 1)}…` : value;

    const svg = `
      <svg viewBox="0 0 ${width} ${height}" role="group" aria-label="${escapeHtml(options.label || '개념 관계 시각화')}">
        <defs>
          <marker id="atlas-arrow-required" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 z" fill="var(--atlas-blue)"></path>
          </marker>
          <marker id="atlas-arrow-helpful" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 z" fill="var(--atlas-teal)"></path>
          </marker>
        </defs>
        <g aria-hidden="true">
          ${clippedEdges.map((edge) => {
            const source = positions.get(edge.source);
            const target = positions.get(edge.target);
            const prerequisiteClass = edge.category === 'helpful'
              ? 'atlas-edge atlas-edge--prerequisite atlas-edge--helpful'
              : 'atlas-edge atlas-edge--prerequisite atlas-edge--required';
            const className = edge.type === 'prerequisite' ? prerequisiteClass : 'atlas-edge';
            const marker = edge.category === 'helpful' ? 'atlas-arrow-helpful' : 'atlas-arrow-required';
            return `<line class="${className}" x1="${source.x}" y1="${source.y}" x2="${target.x}" y2="${target.y}" ${edge.type === 'prerequisite' ? `marker-end="url(#${marker})"` : ''}></line>`;
          }).join('')}
        </g>
        <g>
          ${nodes.map((node) => {
            const position = positions.get(node.id);
            const href = localUrl(node.url || node.href || '#');
            return `
              <a class="atlas-node" href="${escapeHtml(href)}" aria-label="${escapeHtml(node.title)}"
                ${options.currentId === node.id ? 'aria-current="true"' : ''}>
                <circle cx="${position.x}" cy="${position.y}" r="32"></circle>
                <text x="${position.x}" y="${position.y + 51}" text-anchor="middle">${escapeHtml(shorten(node.title))}</text>
              </a>
            `;
          }).join('')}
        </g>
      </svg>
    `;
    container.innerHTML = svg;

    if (listContainer) {
      const outgoing = new Map(nodes.map((node) => [node.id, []]));
      clippedEdges.forEach((edge) => outgoing.get(edge.source)?.push(edge));
      listContainer.innerHTML = `
        <details>
          <summary>텍스트 목록으로 관계 보기 (${nodes.length}개 노드, ${clippedEdges.length}개 관계)</summary>
          <ul>
            ${nodes.map((node) => {
              const relations = outgoing.get(node.id) || [];
              const destinations = relations.map((edge) => {
                const label = edge.type === 'prerequisite'
                  ? edge.category === 'helpful' ? '도움' : '필수'
                  : '관련';
                return `${label}: ${nodeById.get(edge.target)?.title || edge.target}`;
              });
              return `<li>${conceptLink(node)}${destinations.length ? ` → ${escapeHtml(destinations.join(', '))}` : ''}</li>`;
            }).join('')}
          </ul>
        </details>
      `;
    }
  };

  const renderDomainHubs = (concepts) => {
    const container = document.querySelector('#domain-hubs');
    if (!container) return;
    const groups = new Map();
    concepts.forEach((concept) => {
      if (!groups.has(concept.domain)) groups.set(concept.domain, []);
      groups.get(concept.domain).push(concept);
    });
    container.innerHTML = [...groups.entries()]
      .sort((a, b) => (DOMAIN_LABELS[a[0]] || a[0]).localeCompare(DOMAIN_LABELS[b[0]] || b[0], 'ko'))
      .map(([domain, entries]) => `
        <section class="domain-card">
          <h3>${escapeHtml(DOMAIN_LABELS[domain] || domain)}</h3>
          <p class="domain-card__count">${entries.length}개 개념</p>
          <ul>
            ${entries.slice(0, 6).map((concept) => `<li>${conceptLink(concept)}</li>`).join('')}
          </ul>
        </section>
      `).join('');
  };

  const renderAtlas = (manifest) => {
    const controls = document.querySelector('#atlas-controls');
    const graph = document.querySelector('#atlas-graph');
    if (!controls || !graph) return;
    const list = document.querySelector('#atlas-graph-list');
    const { concepts } = conceptIndex(manifest);
    const domains = [...new Set(concepts.map((concept) => concept.domain))].sort();
    controls.innerHTML = `
      <div class="atlas-field">
        <label for="atlas-search">개념·영문·약어 검색</label>
        <input id="atlas-search" type="search" placeholder="예: PID, 최소제곱, resampling">
      </div>
      <div class="atlas-field">
        <label for="atlas-focus">중심 개념</label>
        <select id="atlas-focus">
          <option value="">중심 없이 보기</option>
          ${concepts.map((concept) => `<option value="${escapeHtml(concept.id)}">${escapeHtml(concept.title)}</option>`).join('')}
        </select>
      </div>
      <div class="atlas-field">
        <label for="atlas-scope">주변 범위</label>
        <select id="atlas-scope">
          <option value="1">1단계 이웃</option>
          <option value="2">2단계 이웃</option>
          <option value="all">전체 그래프</option>
        </select>
      </div>
      <div class="atlas-field">
        <label for="atlas-depth">선수관계 깊이</label>
        <select id="atlas-depth">
          <option value="intuition">직관</option>
          <option value="application">계산·적용</option>
          <option value="derivation">유도</option>
          <option value="proof">증명</option>
          <option value="all">모든 깊이</option>
        </select>
      </div>
      <div class="atlas-field">
        <label for="atlas-domain">분야</label>
        <select id="atlas-domain">
          <option value="">모든 분야</option>
          ${domains.map((domain) => `<option value="${escapeHtml(domain)}">${escapeHtml(DOMAIN_LABELS[domain] || domain)}</option>`).join('')}
        </select>
      </div>
      <div class="atlas-field">
        <label for="atlas-mastery">학습 상태</label>
        <select id="atlas-mastery">
          <option value="">모든 상태</option>
          <option value="unseen">아직 안 봄</option>
          <option value="started">학습 시작</option>
          <option value="applied">적용 가능 이상</option>
        </select>
      </div>
    `;

    const allEdges = graphEdges(manifest, concepts, 'concept');
    const initialFocus = new URLSearchParams(window.location.search).get('focus')
      || (concepts.some((concept) => concept.id === 'control.pid') ? 'control.pid' : concepts[0]?.id)
      || '';
    controls.querySelector('#atlas-focus').value = initialFocus;

    const neighborhood = (center, hops, edges) => {
      if (!center || hops === 'all') return new Set(concepts.map((concept) => concept.id));
      const adjacency = new Map(concepts.map((concept) => [concept.id, new Set()]));
      edges.forEach((edge) => {
        adjacency.get(edge.source)?.add(edge.target);
        adjacency.get(edge.target)?.add(edge.source);
      });
      const visited = new Set([center]);
      let frontier = new Set([center]);
      for (let depth = 0; depth < Number(hops); depth += 1) {
        const next = new Set();
        frontier.forEach((id) => {
          adjacency.get(id)?.forEach((neighbor) => {
            if (!visited.has(neighbor)) next.add(neighbor);
          });
        });
        next.forEach((id) => visited.add(id));
        frontier = next;
      }
      return visited;
    };

    const update = () => {
      const query = controls.querySelector('#atlas-search').value.trim().toLocaleLowerCase('ko');
      const focus = controls.querySelector('#atlas-focus').value;
      const scope = controls.querySelector('#atlas-scope').value;
      const selectedDepth = controls.querySelector('#atlas-depth').value;
      const domain = controls.querySelector('#atlas-domain').value;
      const mastery = controls.querySelector('#atlas-mastery').value;
      const depthLimit = selectedDepth === 'all'
        ? Number.POSITIVE_INFINITY
        : UI_DEPTH_LIMIT[selectedDepth];
      const visibleEdges = allEdges.filter((edge) => {
        if (edge.type !== 'prerequisite' || !edge.depth) return true;
        return METADATA_DEPTH_ORDER.indexOf(edge.depth) <= depthLimit;
      });
      const visibleIds = query
        ? new Set(concepts.map((concept) => concept.id))
        : neighborhood(focus, scope, visibleEdges);
      const filtered = concepts.filter((concept) => {
        const haystack = [concept.title, concept.id, concept.summary, ...concept.aliases].join(' ').toLocaleLowerCase('ko');
        const rank = Number(progress.concepts[concept.id] || 0);
        const masteryMatches = !mastery
          || (mastery === 'unseen' && rank === 0)
          || (mastery === 'started' && rank >= 1)
          || (mastery === 'applied' && rank >= 2);
        return visibleIds.has(concept.id)
          && (!query || haystack.includes(query))
          && (!domain || concept.domain === domain)
          && masteryMatches;
      }).slice(0, 60);
      renderGraph(graph, list, filtered, visibleEdges, {
        label: '개념 선수관계 지도',
        currentId: focus,
      });
    };

    controls.addEventListener('input', update);
    controls.addEventListener('change', update);
    document.addEventListener('atlas:progress', update);
    update();
    renderDomainHubs(concepts);
  };

  const renderProofGraph = (manifest) => {
    const graph = document.querySelector('#proof-graph');
    if (!graph) return;
    const list = document.querySelector('#proof-graph-list');
    const proofs = arrayOf(manifest.proofs).map((proof) => ({
      ...proof,
      id: proof.id || proof.slug || '',
      title: proof.title || proof.theorem || proof.id || '제목 없음',
      url: proof.url || proof.href || '#',
      dependencies: arrayOf(proof.dependencies || proof.prerequisites),
    }));
    renderGraph(graph, list, proofs, graphEdges(manifest, proofs, 'proof'), {
      label: '증명 의존관계 지도',
    });
  };

  const normalizePathSteps = (path) => arrayOf(path.steps || path.concepts || path.sequence)
    .map((step) => typeof step === 'string' ? { id: step } : step);

  const renderPaths = (manifest) => {
    const container = document.querySelector('#learning-paths');
    if (!container) return;
    const { byId } = conceptIndex(manifest);
    let paths = arrayOf(manifest.paths);
    if (!paths.length) {
      paths = [
        { id: 'pid', title: 'PID를 먼저 이해하기', summary: '미적분의 직관만으로 시작해 폐루프 제어까지 갑니다.', steps: ['pid-controller'] },
        { id: 'kalman', title: 'Kalman Filter', summary: '최소제곱에서 Gaussian 상태추정으로 연결합니다.', steps: ['least-squares', 'kalman-filter'] },
        { id: 'particle-filter', title: 'Particle Filter 완전 경로', summary: '중요도표본추출에서 SIS·SMC·재표본화까지 빠짐없이 잇습니다.', steps: ['importance-sampling', 'sis', 'resampling', 'particle-filter'] },
        { id: 'mcmc', title: 'MCMC 완전 경로', summary: 'Markov chain과 상세균형에서 Metropolis–Hastings로 갑니다.', steps: ['markov-chain', 'detailed-balance', 'metropolis-hastings'] },
      ];
    }
    container.innerHTML = paths.map((path) => {
      const steps = normalizePathSteps(path);
      const completed = steps.filter((step) => Number(progress.concepts[itemId(step)] || 0) >= 1).length;
      const percent = steps.length ? Math.round((100 * completed) / steps.length) : 0;
      return `
        <article class="path-card">
          <h3>${path.url ? `<a href="${escapeHtml(localUrl(path.url))}">${escapeHtml(path.title || path.id)}</a>` : escapeHtml(path.title || path.id)}</h3>
          <p>${escapeHtml(path.summary || path.one_line || path.description || '')}</p>
          <p class="path-card__meta">${completed}/${steps.length} 시작 · ${percent}%</p>
          <div class="progress-meter" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent}"><span style="width:${percent}%"></span></div>
          <ol class="path-card__steps">
            ${steps.map((step) => {
              const id = itemId(step);
              const concept = byId.get(id) || { id, title: step.title || id, url: step.url || '#' };
              return `<li>${conceptLink(concept)}</li>`;
            }).join('')}
          </ol>
        </article>
      `;
    }).join('');
    document.addEventListener('atlas:progress', () => renderPaths(manifest), { once: true });
  };

  const installProgressCenter = () => {
    const target = document.querySelector('#progress-center');
    const exportLink = document.querySelector('a[href="#progress-export"]');

    const exportProgress = () => {
      const masteryThresholds = {
        intuition: 1,
        application: 2,
        analysis: 2,
        implementation: 2,
        derivation: 3,
        proof: 4,
        teaching: 5,
      };
      const items = Object.fromEntries(Object.entries(progress.concepts).map(([id, value]) => {
        const rank = Number(value || 0);
        const mastery = Object.fromEntries(Object.entries(masteryThresholds).map(([depth, threshold]) => {
          const status = rank >= threshold ? 'mastered' : rank === threshold - 1 ? 'learning' : 'not_started';
          return [depth, status];
        }));
        return [id, { seen: rank > 0, mastery }];
      }));
      const payload = JSON.stringify({
        schema_version: '1.0.0',
        exported_at: new Date().toISOString(),
        items,
        learning_stack: [],
        ui_state: {
          depth: progress.depth,
          bookmarks: progress.bookmarks,
          favorites: progress.favorites,
          last_read: progress.lastRead,
        },
      }, null, 2);
      const blob = new Blob([payload], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `robotics-math-atlas-progress-${new Date().toISOString().slice(0, 10)}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
    };

    const importInput = document.createElement('input');
    importInput.type = 'file';
    importInput.accept = 'application/json,.json';
    importInput.hidden = true;
    importInput.addEventListener('change', async () => {
      const file = importInput.files?.[0];
      if (!file) return;
      try {
        const incoming = JSON.parse(await file.text());
        if (incoming.schema_version === '1.0.0' && incoming.items) {
          const thresholds = {
            intuition: 1,
            application: 2,
            analysis: 2,
            implementation: 2,
            derivation: 3,
            proof: 4,
            teaching: 5,
          };
          progress.concepts = Object.fromEntries(Object.entries(incoming.items).map(([id, item]) => {
            const mastered = Object.entries(item.mastery || {})
              .filter(([, status]) => status === 'mastered')
              .map(([depth]) => thresholds[depth] || 0);
            const rank = Math.max(item.seen ? 1 : 0, ...mastered);
            return [id, rank];
          }));
          progress.depth = incoming.ui_state?.depth || {};
          progress.bookmarks = incoming.ui_state?.bookmarks || {};
          progress.favorites = incoming.ui_state?.favorites || {};
          progress.lastRead = incoming.ui_state?.last_read || {};
        } else if (incoming.format === 'robotics-math-atlas-progress' || incoming.concepts) {
          // Import the development-preview format used before schema version 1.0.0.
          progress.concepts = incoming.concepts || {};
          progress.depth = incoming.depth || {};
          progress.bookmarks = incoming.bookmarks || {};
          progress.favorites = incoming.favorites || {};
          progress.lastRead = incoming.lastRead || {};
        } else {
          throw new Error('지원하지 않는 파일 형식입니다.');
        }
        migrateProgressPaths(progress);
        saveProgress();
        window.location.reload();
      } catch (error) {
        window.alert(`진도 파일을 불러오지 못했습니다: ${error.message}`);
      }
    });
    document.body.append(importInput);

    exportLink?.addEventListener('click', (event) => {
      event.preventDefault();
      exportProgress();
    });

    if (target) {
      target.innerHTML = `
        <button type="button" class="atlas-button atlas-button--primary" data-progress-export>진도 JSON 내보내기</button>
        <button type="button" class="atlas-button" data-progress-import>진도 JSON 가져오기</button>
        <button type="button" class="atlas-button" data-progress-reset>이 브라우저 진도 초기화</button>
      `;
      target.querySelector('[data-progress-export]').addEventListener('click', exportProgress);
      target.querySelector('[data-progress-import]').addEventListener('click', () => importInput.click());
      target.querySelector('[data-progress-reset]').addEventListener('click', () => {
        if (window.confirm('이 브라우저에 저장된 숙달 상태, 깊이 선택, 즐겨찾기, 책갈피와 마지막 읽기 위치를 모두 지울까요?')) {
          localStorage.removeItem(STORAGE_KEY);
          window.location.reload();
        }
      });
    }
  };

  const installReadingProgress = () => {
    const article = document.querySelector('#quarto-document-content');
    if (!article || document.querySelector('.reading-progress')) return;
    // 읽기 도구는 긴 본문(개념 장·증명·실습)에서만 의미가 있다 —
    // 홈·아틀라스·커리큘럼 같은 허브 페이지에서는 진행률이 소음이라 띄우지 않는다.
    if (!/\/(content|courseware)\//.test(window.location.pathname)) return;
    const track = document.createElement('div');
    track.className = 'reading-progress';
    track.setAttribute('aria-hidden', 'true');
    track.innerHTML = '<span></span>';
    document.body.prepend(track);
    const indicator = track.firstElementChild;
    const headingMap = new Map();
    article.querySelectorAll('section[id] > h2, section[id] > h3, h2[id], h3[id]').forEach((heading) => {
      if (heading.closest('.concept-toolbar, .page-glossary')) return;
      const section = heading.closest('section[id]');
      const id = heading.id || section?.id;
      if (!id || headingMap.has(id)) return;
      headingMap.set(id, {
        id,
        title: heading.textContent.trim(),
        level: heading.tagName.toLowerCase(),
        anchor: section || heading,
      });
    });
    const headings = [...headingMap.values()];

    const quickStart = article.querySelector('.concept-hero');
    if (quickStart && !quickStart.id) quickStart.id = 'concept-quick-start';
    const quickStartHref = quickStart ? `#${quickStart.id}` : '#';
    const pageKey = currentPageKey();
    const pageTitle = document.querySelector('h1.title')?.textContent.trim() || document.title;
    const initialRecord = progress.lastRead[pageKey];
    let activeHeading = headings[0] || null;
    let userMoved = false;
    let lastReadTimer = null;

    const tools = document.createElement('aside');
    tools.className = 'reader-tools';
    tools.setAttribute('aria-label', '읽기 위치와 바로가기');
    tools.innerHTML = `
      <button type="button" class="reader-tools__collapse" data-reader-collapse aria-expanded="true" title="읽기 도구 접기/펼치기">
        <span data-collapse-icon aria-hidden="true">⌄</span><span data-collapse-label></span>
      </button>
      <div class="reader-tools__actions">
        ${quickStart ? `<a class="reader-tool" href="${escapeHtml(quickStartHref)}" title="30초 핵심으로"><span aria-hidden="true">↑</span><span>핵심</span></a>` : ''}
        <button type="button" class="reader-tool" data-reader-favorite aria-pressed="false" aria-keyshortcuts="Alt+F" title="이 페이지 즐겨찾기 (Alt+F)"><span aria-hidden="true">☆</span><span>즐겨찾기</span></button>
        <button type="button" class="reader-tool" data-reader-bookmark aria-pressed="false" aria-keyshortcuts="Alt+B" title="현재 절 책갈피 (Alt+B)"><span aria-hidden="true">◇</span><span>책갈피</span></button>
        <details class="reader-tools__toc">
          <summary class="reader-tool" aria-keyshortcuts="Alt+T" title="이 페이지 목차 (Alt+T)"><span aria-hidden="true">☷</span><span>목차</span></summary>
          <nav aria-label="이 페이지의 절 바로가기">
            <ol data-reader-toc></ol>
          </nav>
        </details>
        <details class="reader-tools__saved">
          <summary class="reader-tool" title="저장한 즐겨찾기와 책갈피"><span aria-hidden="true">▣</span><span>저장 목록</span></summary>
          <nav aria-label="저장한 즐겨찾기와 책갈피" data-reader-saved></nav>
        </details>
        <button type="button" class="reader-tool reader-tool--resume" data-reader-resume hidden>저장 위치로</button>
      </div>
      <label class="reader-tools__position">
        <span data-reader-position>읽기 위치</span>
        <input type="range" min="0" max="100" value="0" step="0.1" data-reader-range aria-label="이 페이지 읽기 위치" aria-valuetext="0%">
        <output data-reader-percent>0%</output>
      </label>
    `;
    document.body.append(tools);
    document.body.classList.add('atlas-reader-active');

    // 기본은 접힘 — 도구가 필요할 때만 펼친다. 선택은 기억된다.
    const collapseButton = tools.querySelector('[data-reader-collapse]');
    const COLLAPSE_KEY = 'atlas-reader-tools-collapsed';
    const applyCollapsed = (collapsed) => {
      tools.classList.toggle('reader-tools--collapsed', collapsed);
      document.body.classList.toggle('atlas-reader-collapsed', collapsed);
      collapseButton.setAttribute('aria-expanded', String(!collapsed));
      collapseButton.querySelector('[data-collapse-icon]').textContent = collapsed ? '☷' : '⌄';
      collapseButton.querySelector('[data-collapse-label]').textContent = collapsed ? ' 읽기 도구' : '';
      try { localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0'); } catch (error) { /* 사생활 모드 등 */ }
    };
    collapseButton.addEventListener('click', () => {
      applyCollapsed(!tools.classList.contains('reader-tools--collapsed'));
    });
    let initialCollapsed = true;
    try {
      const storedCollapse = localStorage.getItem(COLLAPSE_KEY);
      if (storedCollapse !== null) initialCollapsed = storedCollapse === '1';
    } catch (error) { /* 저장 불가 환경에서는 기본값 유지 */ }
    applyCollapsed(initialCollapsed);

    const favoriteButton = tools.querySelector('[data-reader-favorite]');
    const bookmarkButton = tools.querySelector('[data-reader-bookmark]');
    const resumeButton = tools.querySelector('[data-reader-resume]');
    const range = tools.querySelector('[data-reader-range]');
    const positionLabel = tools.querySelector('[data-reader-position]');
    const percentLabel = tools.querySelector('[data-reader-percent]');
    const toc = tools.querySelector('.reader-tools__toc');
    const tocList = tools.querySelector('[data-reader-toc]');
    const saved = tools.querySelector('.reader-tools__saved');
    const savedPanel = tools.querySelector('[data-reader-saved]');

    const visibleHeadings = () => headings.filter((heading) => (
      !heading.anchor.closest('.depth-hidden')
      && !heading.anchor.hidden
      && heading.anchor.getClientRects().length > 0
    ));

    // 우측 목차 재구성: 본문 절이 depth 게이팅 div 안에 있으면 Quarto TOC가
    // 앞 몇 항목에서 끊긴다 — 지금 보이는 절 전체로 다시 채우고, 깊이가
    // 바뀌면 다시 그린다. 현재 절 하이라이트는 스크롤 갱신 루프가 담당한다.
    const originalTocCount = document.querySelector('nav#TOC')?.querySelectorAll('a').length ?? 0;
    let outlineLinks = null;
    const renderOutline = () => {
      // Quarto가 모바일 내비용으로 목차를 복제하므로 모든 사본을 함께 갱신한다.
      const navs = document.querySelectorAll('nav#TOC');
      if (!navs.length) return;
      const entries = visibleHeadings();
      if (entries.length <= originalTocCount) return;
      navs.forEach((nav) => {
        const list = document.createElement('ul');
        list.className = 'atlas-outline';
        entries.forEach((heading) => {
          const item = document.createElement('li');
          item.className = heading.level === 'h3' ? 'toc-l3' : 'toc-l2';
          const link = document.createElement('a');
          link.href = `#${heading.id}`;
          link.textContent = heading.title;
          item.appendChild(link);
          list.appendChild(item);
        });
        nav.querySelectorAll('ul').forEach((old) => old.remove());
        nav.appendChild(list);
      });
      outlineLinks = true;
    };
    renderOutline();
    document.addEventListener('atlas:depth', () => window.requestAnimationFrame(renderOutline));
    // Quarto의 목차 복제가 우리 재구성보다 늦을 수 있어 한 번 더 동기화한다.
    window.setTimeout(renderOutline, 1200);

    const renderToc = () => {
      const current = visibleHeadings();
      tocList.innerHTML = current
        .map((heading) => `<li class="reader-tools__toc-${heading.level}"><a href="#${escapeHtml(heading.id)}">${escapeHtml(heading.title)}</a></li>`)
        .join('');
      tocList.querySelectorAll('a').forEach((link) => {
        link.addEventListener('click', () => { toc.open = false; });
      });
    };

    const renderSaved = () => {
      const favorites = Object.values(progress.favorites)
        .filter((entry) => entry?.url)
        .sort((left, right) => String(right.updatedAt || '').localeCompare(String(left.updatedAt || '')));
      const bookmarks = Object.values(progress.bookmarks)
        .filter((entry) => entry?.url)
        .sort((left, right) => String(right.updatedAt || '').localeCompare(String(left.updatedAt || '')));
      savedPanel.innerHTML = `
        <h3>즐겨찾기 ${favorites.length}개</h3>
        ${favorites.length ? `<ul>${favorites.map((entry) => `<li><a href="${escapeHtml(safeSavedUrl(entry.url))}">${escapeHtml(entry.title || entry.url)}</a></li>`).join('')}</ul>` : '<p>저장한 페이지가 없습니다.</p>'}
        <h3>절 책갈피 ${bookmarks.length}개</h3>
        ${bookmarks.length ? `<ul>${bookmarks.map((entry) => `<li><a href="${escapeHtml(safeSavedUrl(entry.url))}">${escapeHtml(entry.pageTitle || '')}<small>${escapeHtml(entry.sectionTitle || '페이지 시작')}</small></a></li>`).join('')}</ul>` : '<p>저장한 절이 없습니다.</p>'}
      `;
      savedPanel.querySelectorAll('a').forEach((link) => {
        link.addEventListener('click', () => { saved.open = false; });
      });
    };

    const bookmarkKey = () => `${pageKey}#${activeHeading?.id || 'top'}`;
    const refreshActions = () => {
      const favorite = Boolean(progress.favorites[pageKey]);
      favoriteButton.setAttribute('aria-pressed', String(favorite));
      favoriteButton.querySelector('[aria-hidden]').textContent = favorite ? '★' : '☆';
      const bookmarked = Boolean(progress.bookmarks[bookmarkKey()]);
      bookmarkButton.setAttribute('aria-pressed', String(bookmarked));
      bookmarkButton.querySelector('[aria-hidden]').textContent = bookmarked ? '◆' : '◇';
    };

    let lastComputedRatio = Number(initialRecord?.ratio || 0);
    const commitLastRead = (ratio = lastComputedRatio) => {
      if (!userMoved) return;
      progress.lastRead[pageKey] = {
        url: siteRelativePath(window.location.href),
        title: pageTitle,
        sectionId: activeHeading?.id || '',
        sectionTitle: activeHeading?.title || '',
        ratio,
        updatedAt: new Date().toISOString(),
      };
      progress.updatedAt = new Date().toISOString();
      persistProgress();
    };
    const saveLastRead = (ratio) => {
      lastComputedRatio = ratio;
      if (!userMoved) return;
      window.clearTimeout(lastReadTimer);
      lastReadTimer = window.setTimeout(() => commitLastRead(ratio), 500);
    };

    let scheduled = false;
    const update = () => {
      const start = article.getBoundingClientRect().top + window.scrollY;
      const distance = Math.max(1, article.offsetHeight - window.innerHeight);
      const ratio = Math.max(0, Math.min(1, (window.scrollY - start) / distance));
      const percent = Math.round(ratio * 100);
      indicator.style.width = `${(ratio * 100).toFixed(2)}%`;
      range.value = (ratio * 100).toFixed(1);
      percentLabel.value = `${percent}%`;
      percentLabel.textContent = `${percent}%`;
      const currentHeadings = visibleHeadings();
      const marker = window.scrollY + Math.min(180, window.innerHeight * 0.24);
      activeHeading = currentHeadings.reduce((current, heading) => (
        heading.anchor.getBoundingClientRect().top + window.scrollY <= marker ? heading : current
      ), currentHeadings[0] || null);
      const sectionIndex = Math.max(0, currentHeadings.indexOf(activeHeading));
      positionLabel.textContent = currentHeadings.length
        ? `절 ${sectionIndex + 1}/${currentHeadings.length} · ${activeHeading.title}`
        : '읽기 위치';
      // 우측 목차의 현재 절 하이라이트 + 접힌 도구막대에도 현재 절 표시
      // (Quarto가 모바일용으로 목차를 복제하므로 모든 사본에 브로드캐스트)
      if (outlineLinks && activeHeading) {
        document.querySelectorAll('ul.atlas-outline a').forEach((link) => {
          link.classList.toggle('active', link.getAttribute('href') === `#${activeHeading.id}`);
        });
      }
      if (tools.classList.contains('reader-tools--collapsed')) {
        const shortTitle = activeHeading && currentHeadings.length
          ? `${activeHeading.title.slice(0, 14)}${activeHeading.title.length > 14 ? '…' : ''}`
          : '읽기 도구';
        collapseButton.querySelector('[data-collapse-label]').textContent =
          currentHeadings.length
            ? ` 절 ${sectionIndex + 1}/${currentHeadings.length} · ${shortTitle}`
            : ' 읽기 도구';
      }
      range.setAttribute(
        'aria-valuetext',
        currentHeadings.length
          ? `${percent}%, 절 ${sectionIndex + 1}/${currentHeadings.length}, ${activeHeading.title}`
          : `${percent}%`,
      );
      refreshActions();
      saveLastRead(ratio);
      scheduled = false;
    };
    const schedule = () => {
      if (scheduled) return;
      scheduled = true;
      window.requestAnimationFrame(update);
    };
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule, { passive: true });
    const markUserMovement = () => { userMoved = true; };
    window.addEventListener('wheel', markUserMovement, { passive: true });
    window.addEventListener('touchmove', markUserMovement, { passive: true });
    document.addEventListener('keydown', (event) => {
      const target = event.target;
      if (target instanceof HTMLElement
        && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName))) return;
      if (['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '].includes(event.key)) {
        markUserMovement();
      }
    }, { capture: true });
    range.addEventListener('input', () => {
      userMoved = true;
      const start = article.getBoundingClientRect().top + window.scrollY;
      const distance = Math.max(1, article.offsetHeight - window.innerHeight);
      window.scrollTo({ top: start + (Number(range.value) / 100) * distance, behavior: 'auto' });
    });
    favoriteButton.addEventListener('click', () => {
      if (progress.favorites[pageKey]) delete progress.favorites[pageKey];
      else {
        progress.favorites[pageKey] = {
          url: pageKey,
          title: pageTitle,
          updatedAt: new Date().toISOString(),
        };
      }
      saveProgress();
      refreshActions();
      renderSaved();
    });
    bookmarkButton.addEventListener('click', () => {
      const key = bookmarkKey();
      if (progress.bookmarks[key]) delete progress.bookmarks[key];
      else {
        progress.bookmarks[key] = {
          url: `${pageKey}${activeHeading?.id ? `#${activeHeading.id}` : ''}`,
          pageTitle,
          sectionId: activeHeading?.id || '',
          sectionTitle: activeHeading?.title || '',
          updatedAt: new Date().toISOString(),
        };
      }
      saveProgress();
      refreshActions();
      renderSaved();
    });
    if (initialRecord?.ratio > 0.02) {
      resumeButton.hidden = false;
      resumeButton.title = `${initialRecord.sectionTitle || '이전 위치'} · ${Math.round(initialRecord.ratio * 100)}%`;
      resumeButton.addEventListener('click', () => {
        userMoved = true;
        const start = article.getBoundingClientRect().top + window.scrollY;
        const distance = Math.max(1, article.offsetHeight - window.innerHeight);
        const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        window.scrollTo({
          top: start + initialRecord.ratio * distance,
          behavior: reduceMotion ? 'auto' : 'smooth',
        });
        resumeButton.hidden = true;
      });
    }
    [toc, saved].forEach((panel) => {
      panel.addEventListener('toggle', () => {
        if (!panel.open) return;
        [toc, saved].filter((candidate) => candidate !== panel).forEach((candidate) => {
          candidate.open = false;
        });
      });
    });
    document.addEventListener('atlas:depth', () => {
      renderToc();
      schedule();
    });
    window.addEventListener('pagehide', () => {
      window.clearTimeout(lastReadTimer);
      commitLastRead();
    });
    document.addEventListener('keydown', (event) => {
      if (!event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.key.toLowerCase() === 'f') {
        event.preventDefault();
        favoriteButton.click();
      } else if (event.key.toLowerCase() === 'b') {
        event.preventDefault();
        bookmarkButton.click();
      } else if (event.key.toLowerCase() === 't') {
        event.preventDefault();
        toc.open = !toc.open;
      }
    });
    refreshActions();
    renderToc();
    renderSaved();
    update();
  };

  const installPageGlossary = () => {
    const article = document.querySelector('#quarto-document-content');
    if (!article) return;
    const existingGlossary = article.querySelector('.page-glossary');
    const terms = new Map();
    article.querySelectorAll('.atlas-term[data-definition], abbr[title]').forEach((element) => {
      const label = element.dataset.term || element.textContent.trim();
      const definition = element.dataset.definition || element.getAttribute('title') || '';
      if (!label || !definition) return;
      const english = String(element.dataset.en || '').trim();
      const displayEnglish = english
        && !label.toLocaleLowerCase('en').includes(english.toLocaleLowerCase('en'))
        ? english
        : '';
      const key = label.toLocaleLowerCase('ko');
      if (!terms.has(key)) terms.set(key, { label, definition, english: displayEnglish });
      element.setAttribute('tabindex', '0');
      if (!element.getAttribute('title')) element.setAttribute('title', definition);
      element.setAttribute('aria-label', `${label}: ${definition}`);
    });
    if (existingGlossary || !terms.size) return;
    const glossary = document.createElement('details');
    glossary.className = 'page-glossary';
    glossary.innerHTML = `
      <summary>이 페이지의 용어 · Glossary (${terms.size})</summary>
      <dl>
        ${[...terms.values()].map((term) => `
          <dt>${escapeHtml(term.label)}${term.english ? ` <small lang="en">${escapeHtml(term.english)}</small>` : ''}</dt>
          <dd>${escapeHtml(term.definition)}</dd>
        `).join('')}
      </dl>
    `;
    article.append(glossary);
  };

  const installMotion = () => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const targets = document.querySelectorAll([
      '.concept-hero',
      '.concept-toolbar',
      '.key-takeaway',
      '.term-card',
      '.annotation-note',
      '.formula-card',
      '.mistake-card',
      '.history-card',
      '.learning-objectives',
      '.glossary-entry',
      '.engineering-meaning',
      '.assumption-box',
      '.failure-mode',
    ].join(','));
    if (!targets.length) return;
    document.documentElement.classList.add('atlas-enhanced');
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
    targets.forEach((target) => {
      if (target.classList.contains('atlas-reveal')) return;
      target.classList.add('atlas-reveal');
      observer.observe(target);
    });
  };

  const showLoadError = (error) => {
    document.querySelectorAll('#atlas-graph, #proof-graph, #learning-paths, #domain-hubs').forEach((target) => {
      if (target.children.length) return;
      target.innerHTML = `<div class="atlas-error">아틀라스 데이터를 불러오지 못했습니다.<br>${escapeHtml(error.message)}</div>`;
    });
  };

  const boot = async () => {
    injectReturnBanner();
    installProgressCenter();
    installReadingProgress();
    installPageGlossary();
    const manifestTargets = '#concept-meta[data-concept-id], #atlas-graph, #proof-graph, #learning-paths, #domain-hubs';
    if (!document.querySelector(manifestTargets)) {
      installMotion();
      return;
    }
    const markerManifest = document.querySelector('#concept-meta[data-manifest-url]')?.dataset.manifestUrl;
    const manifestUrl = markerManifest
      ? new URL(markerManifest, document.baseURI).href
      : MANIFEST_URL;
    try {
      const response = await fetch(manifestUrl, { cache: 'no-cache' });
      if (!response.ok) throw new Error(`manifest HTTP ${response.status}`);
      const manifest = await response.json();
      renderConceptToolbar(manifest);
      renderAtlas(manifest);
      renderProofGraph(manifest);
      renderPaths(manifest);
      installMotion();
    } catch (error) {
      console.error('Robotics Math Atlas:', error);
      showLoadError(error);
      installMotion();
    }
  };

  if (typeof window.__ATLAS_TEST_HOOK__ === 'function') {
    window.__ATLAS_TEST_HOOK__({
      currentPageKey,
      migrateProgressPaths,
      projectRootUrl,
      safeSavedUrl,
      siteRelativePath,
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
})();
