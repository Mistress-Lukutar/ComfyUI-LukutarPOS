/*
 * File:   label_canvas.js
 * Brief:  Frontend behaviour of the Label Canvas node.
 * Author: Mistress-Lukutar
 * Date:   2026-09-03
 * Version: v0.1.0
 *
 * The width/height dot widgets only make sense for the "custom" size
 * preset; with a stock preset they are ignored by the backend, so the
 * extension greys them out to make that visible.
 */

import { app } from "../../../scripts/app.js";

const CUSTOM_SIZE = "custom";
const SIZE_WIDGET = "size";
const DIM_WIDGETS = ["width_dots", "height_dots"];

app.registerExtension({
    name: "LukutarPOS.LabelCanvas",

    beforeRegisterNodeDef(nodeType) {
        if (nodeType.name !== "LabelCanvas") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);

            const sizeWidget = this.widgets?.find((w) => w.name === SIZE_WIDGET);
            const dimWidgets = (this.widgets ?? []).filter((w) =>
                DIM_WIDGETS.includes(w.name)
            );
            if (!sizeWidget || dimWidgets.length === 0) return result;

            const syncDisabled = () => {
                const custom = sizeWidget.value === CUSTOM_SIZE;
                for (const widget of dimWidgets) widget.disabled = !custom;
                this.graph?.setDirtyCanvas(true, true);
            };

            const callback = sizeWidget.callback;
            sizeWidget.callback = function () {
                const r = callback?.apply(this, arguments);
                syncDisabled();
                return r;
            };

            // Saved workflows restore widget values after onNodeCreated.
            const onConfigure = this.onConfigure;
            this.onConfigure = function () {
                const r = onConfigure?.apply(this, arguments);
                syncDisabled();
                return r;
            };

            syncDisabled();
            return result;
        };
    },
});
