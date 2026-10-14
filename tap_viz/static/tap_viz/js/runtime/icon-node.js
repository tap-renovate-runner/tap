/**
 * icon-node.js — Icon-centric node representation for TAP Viz.
 *
 * An icon node is the top-most representation of a thing: a bordered, filled card with the type icon in
 * the centre and the name below the card. It says "this thing is here" and shows nothing inside. The
 * standard node, by contrast, is a box with the name in the middle and the type icon as a small badge in
 * the upper-left corner (badge-nodes.js).
 *
 * A layout module calls applyIconNodes(cy, ...) from its execute(context), BEFORE projectNested, with the
 * nodes it chose. The primitive marks them (`_is_icon_node`, drawn by the `node[_is_icon_node]` rule in
 * panel-graph.js), records each one's size (`_icon_w`, `_icon_h`) and sets that size on the node.
 * projectNested then treats an icon node as a leaf of exactly that size and hides what it would have
 * contained (nested-projection.js).
 *
 * The size is an input, never a constant: it is settable per call, per node (write `_icon_w` / `_icon_h`),
 * and after the fact with handle.resize(), so a later change can pre-scale the card for zoom and morph it
 * to the standard view. See spec-viz-icon-node.md.
 *
 * Idempotent per iconNodeId — safe to re-run across elevation transitions.
 */

export const ICON_NODE_HIDDEN_BY = "_icon_hidden_by";

const DEFAULT_SIZE = 96;
const DEFAULT_ICON_RATIO = 0.6;

// cy → Map(iconNodeId → ids of the nodes that pass changed)
const _passes = new WeakMap();

function _validSize(width, height) {
    return Number.isFinite(width) && Number.isFinite(height) && width > 0 && height > 0;
}

function _passMap(cy) {
    let m = _passes.get(cy);
    if (!m) {
        m = new Map();
        _passes.set(cy, m);
    }
    return m;
}

function _style(node, width, height, ratio) {
    const pct = Math.round(ratio * 100) + "%";
    node.style({"width": width, "height": height, "background-width": pct, "background-height": pct});
}

function _restore(cy, key) {
    const m = _passMap(cy);
    const ids = m.get(key);
    if (!ids) return;
    m.delete(key);
    ids.forEach((id) => {
        const node = cy.getElementById(id);
        if (node.empty()) return;
        // What nesting hid inside this node comes back with it.
        cy.nodes().filter((n) => n.data(ICON_NODE_HIDDEN_BY) === id).forEach((n) => {
            n.removeData(ICON_NODE_HIDDEN_BY);
            n.removeClass("tap-elevation-hidden");
        });
        node.removeData("_is_icon_node _icon_key _icon_w _icon_h _icon_ratio");
        node.removeStyle("width height background-width background-height");
    });
}

/**
 * Mark nodes as icon nodes.
 *
 * @param {cytoscape.Core} cy
 * @param {Object} opts
 * @param {cytoscape.Collection} opts.members The nodes to show as icon nodes.
 * @param {number} [opts.width=96] Card width in model units.
 * @param {number} [opts.height=96] Card height in model units.
 * @param {number} [opts.iconRatio=0.6] The icon's share of the card.
 * @param {string} [opts.iconNodeId="default"] Key that makes a re-run replace the last pass.
 * @returns {{destroy: Function, resize: Function, count: number}}
 */
export function applyIconNodes(cy, opts = {}) {
    const key = opts.iconNodeId || "default";
    _restore(cy, key);

    const members = opts.members && opts.members.length ? opts.members : cy.collection();
    const width = opts.width === undefined ? DEFAULT_SIZE : opts.width;
    const height = opts.height === undefined ? DEFAULT_SIZE : opts.height;
    const ratio = opts.iconRatio === undefined ? DEFAULT_ICON_RATIO : opts.iconRatio;
    if (!_validSize(width, height)) {
        throw new Error("applyIconNodes: width and height must be positive numbers");
    }

    const ids = [];
    members.forEach((node) => {
        // A node may carry its own size already (written by the layout before the call).
        const w = Number(node.data("_icon_w")) > 0 ? Number(node.data("_icon_w")) : width;
        const h = Number(node.data("_icon_h")) > 0 ? Number(node.data("_icon_h")) : height;
        node.data({_is_icon_node: true, _icon_key: key, _icon_w: w, _icon_h: h, _icon_ratio: ratio});
        _style(node, w, h, ratio);
        ids.push(node.id());
    });
    _passMap(cy).set(key, ids);

    return {
        count: ids.length,
        destroy() {
            _restore(cy, key);
        },
        /** Change the size of every node this call applied to. Neighbours are not re-placed; re-run the layout. */
        resize(size) {
            const w = size && size.width, h = size && size.height;
            if (!_validSize(w, h)) return false;
            ids.forEach((id) => {
                const node = cy.getElementById(id);
                if (node.empty()) return;
                node.data({_icon_w: w, _icon_h: h});
                _style(node, w, h, Number(node.data("_icon_ratio")) || ratio);
            });
            return true;
        },
    };
}
