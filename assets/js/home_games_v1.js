(function () {
  const grid = document.getElementById("home-games-grid");
  if (!grid) {
    return;
  }

  const MAX_HOME_GAMES = 48;

  const CATEGORY_RULES = [
    {
      label: "Racing",
      icon: "racing",
      patterns: [/drift|moto|car|truck|racing|madalin|parking|drive|traffic|rush|x3m/i],
    },
    {
      label: "Shooter",
      icon: "shooter",
      patterns: [/shoot|sniper|gun|shell|deadshot|zombie|war|krunker|voxiom|fps/i],
    },
    {
      label: "Puzzle",
      icon: "puzzle",
      patterns: [/puzzle|2048|wordle|sort|quiz|bob|connect|sudoku|chess/i],
    },
    {
      label: "IO",
      icon: "io",
      patterns: [/\.io|\bio\b|moomoo|zombs|surviv|agarpaper|wormate|yohoho|narrow/i],
    },
  ];

  function renderFallbackMessage() {
    grid.innerHTML = '<div class="text-muted fs-sm">Games are loading. Please refresh if this message stays here.</div>';
  }

  function iconMarkup(icon) {
    const icons = {
      racing:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 13h10l1.2-3.2A2 2 0 0 0 16.3 7H7.7a2 2 0 0 0-1.9 2.8L7 13Zm-1.5 1.5 1 2.5h2.3l-.6-1.6h7.6l-.6 1.6h2.3l1-2.5A1.5 1.5 0 0 0 17.1 12H6.9a1.5 1.5 0 0 0-1.4 2.5Z"/></svg>',
      shooter:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h10l4-3v6l-4-3H4v-0Zm2.5-4.5v9H8v-9H6.5Z"/></svg>',
      puzzle:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4h7v4a2 2 0 1 0 2 0V4h7v7h-4a2 2 0 1 0 0 2h4v7h-7v-4a2 2 0 1 0-2 0v4H4v-7h4a2 2 0 1 0 0-2H4V4Z"/></svg>',
      io:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a9 9 0 1 0 9 9 9 9 0 0 0-9-9Zm0 2a7 7 0 0 1 6.9 6H12V5Zm0 14a7 7 0 0 1-6.9-6H12v6Zm2 0v-6h4.9A7 7 0 0 1 14 19Z"/></svg>',
      action:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 2.5 5 5.5.8-4 3.9.9 5.5-4.9-2.6-4.9 2.6.9-5.5-4-3.9 5.5-.8L12 3Z"/></svg>',
    };

    return icons[icon] || icons.action;
  }

  function detectCategory(href, title) {
    const text = (href + " " + title).toLowerCase();

    for (let i = 0; i < CATEGORY_RULES.length; i += 1) {
      const rule = CATEGORY_RULES[i];
      const matched = rule.patterns.some(function (pattern) {
        return pattern.test(text);
      });
      if (matched) {
        return rule;
      }
    }

    return { label: "Action", icon: "action" };
  }

  function buildCardFromNode(sourceNode) {
    const href = sourceNode.getAttribute("href") || "#";
    const image = sourceNode.querySelector("img");
    const titleNode = sourceNode.querySelector("h3");

    if (!image || !titleNode) {
      return null;
    }

    const imgSrc = image.getAttribute("src") || "";
    const imgAlt = image.getAttribute("alt") || titleNode.textContent.trim();
    const title = titleNode.textContent.trim();
    const category = detectCategory(href, title);

    const card = document.createElement("a");
    card.className = "card card-collection";
    card.href = href;
    card.innerHTML =
      '<picture><img class="img-fluid" width="126" height="126"></picture>' +
      '<div class="card-body">' +
      '<div class="card-meta">' +
      '<span class="card-category-icon"></span>' +
      '<span class="card-category-label"></span>' +
      "</div>" +
      "<h3></h3>" +
      "</div>";

    const outImage = card.querySelector("img");
    const outTitle = card.querySelector("h3");
    const outIcon = card.querySelector(".card-category-icon");
    const outLabel = card.querySelector(".card-category-label");

    outImage.src = imgSrc;
    outImage.alt = imgAlt;
    outTitle.textContent = title;
    outIcon.innerHTML = iconMarkup(category.icon);
    outLabel.textContent = category.label;

    return card;
  }

  function shuffle(items) {
    const clone = items.slice();
    for (let i = clone.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      const temp = clone[i];
      clone[i] = clone[j];
      clone[j] = temp;
    }
    return clone;
  }

  fetch("/search.html", { credentials: "same-origin" })
    .then(function (response) {
      if (!response.ok) {
        throw new Error("Failed to load search page");
      }
      return response.text();
    })
    .then(function (html) {
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, "text/html");
      const gameNodes = Array.from(doc.querySelectorAll("a.game-item"));

      if (!gameNodes.length) {
        renderFallbackMessage();
        return;
      }

      const selectedNodes = shuffle(gameNodes).slice(0, MAX_HOME_GAMES);
      const cards = selectedNodes
        .map(buildCardFromNode)
        .filter(function (card) {
          return Boolean(card);
        });

      if (!cards.length) {
        renderFallbackMessage();
        return;
      }

      const fragment = document.createDocumentFragment();
      cards.forEach(function (card) {
        fragment.appendChild(card);
      });

      grid.innerHTML = "";
      grid.appendChild(fragment);
    })
    .catch(function () {
      renderFallbackMessage();
    });
})();
