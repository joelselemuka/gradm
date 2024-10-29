/*!
 * Column visibility buttons for Buttons and DataTables.
 * © SpryMedia Ltd - datatables.net/license
 */
!(function (i) {
  var o, e;
  "function" == typeof define && define.amd
    ? define(
        ["jquery", "datatables.net", "datatables.net-buttons"],
        function (n) {
          return i(n, window, document);
        }
      )
    : "object" == typeof exports
    ? ((o = require("jquery")),
      (e = function (n, t) {
        t.fn.dataTable || require("datatables.net")(n, t),
          t.fn.dataTable.Buttons || require("datatables.net-buttons")(n, t);
      }),
      "undefined" == typeof window
        ? (module.exports = function (n, t) {
            return (
              (n = n || window), (t = t || o(n)), e(n, t), i(t, 0, n.document)
            );
          })
        : (e(window, o), (module.exports = i(o, window, window.document))))
    : i(jQuery, window, document);
})(function (n, t, i) {
  "use strict";
  var e = n.fn.dataTable;
  return (
    n.extend(e.ext.buttons, {
      colvis: function (n, t) {
        var i = null,
          o = {
            extend: "collection",
            init: function (n, t) {
              i = t;
            },
            text: function (n) {
              return n.i18n("buttons.colvis", "Column visibility");
            },
            className: "buttons-colvis",
            closeButton: !1,
            buttons: [
              {
                extend: "columnsToggle",
                columns: t.columns,
                columnText: t.columnText,
              },
            ],
          };
        return (
          n.on("column-reorder.dt" + t.namespace, function () {
            n.button(null, n.button(null, i).node()).collectionRebuild([
              {
                extend: "columnsToggle",
                columns: t.columns,
                columnText: t.columnText,
              },
            ]);
          }),
          o
        );
      },
      columnsToggle: function (n, t) {
        return n
          .columns(t.columns)
          .indexes()
          .map(function (n) {
            return {
              extend: "columnToggle",
              columns: n,
              columnText: t.columnText,
            };
          })
          .toArray();
      },
      columnToggle: function (n, t) {
        return {
          extend: "columnVisibility",
          columns: t.columns,
          columnText: t.columnText,
        };
      },
      columnsVisibility: function (n, t) {
        return n
          .columns(t.columns)
          .indexes()
          .map(function (n) {
            return {
              extend: "columnVisibility",
              columns: n,
              visibility: t.visibility,
              columnText: t.columnText,
            };
          })
          .toArray();
      },
      columnVisibility: {
        columns: void 0,
        text: function (n, t, i) {
          return i._columnText(n, i);
        },
        className: "buttons-columnVisibility",
        action: function (n, t, i, o) {
          var t = t.columns(o.columns),
            e = t.visible();
          t.visible(
            void 0 !== o.visibility ? o.visibility : !(e.length && e[0])
          );
        },
        init: function (i, n, o) {
          var e = this;
          n.attr("data-cv-idx", o.columns),
            i
              .on("column-visibility.dt" + o.namespace, function (n, t) {
                t.bDestroying ||
                  t.nTable != i.settings()[0].nTable ||
                  e.active(i.column(o.columns).visible());
              })
              .on("column-reorder.dt" + o.namespace, function () {
                o.destroying ||
                  (1 === i.columns(o.columns).count() &&
                    (e.text(o._columnText(i, o)),
                    e.active(i.column(o.columns).visible())));
              }),
            this.active(i.column(o.columns).visible());
        },
        destroy: function (n, t, i) {
          n.off("column-visibility.dt" + i.namespace).off(
            "column-reorder.dt" + i.namespace
          );
        },
        _columnText: function (n, t) {
          var i, o;
          return "string" == typeof t.text
            ? t.text
            : ((o = n.column(t.columns).title()),
              (i = n.column(t.columns).index()),
              (o = o
                .replace(/\n/g, " ")
                .replace(/<br\s*\/?>/gi, " ")
                .replace(/<select(.*?)<\/select\s*>/gi, "")),
              (o = e.Buttons.stripHtmlComments(o)),
              (o = e.util.stripHtml(o).trim()),
              t.columnText ? t.columnText(n, i, o) : o);
        },
      },
      colvisRestore: {
        className: "buttons-colvisRestore",
        text: function (n) {
          return n.i18n("buttons.colvisRestore", "Restore visibility");
        },
        init: function (n, t, i) {
          n.columns().every(function () {
            var n = this.init();
            void 0 === n.__visOriginal && (n.__visOriginal = this.visible());
          });
        },
        action: function (n, t, i, o) {
          t.columns().every(function (n) {
            var t = this.init();
            this.visible(t.__visOriginal);
          });
        },
      },
      colvisGroup: {
        className: "buttons-colvisGroup",
        action: function (n, t, i, o) {
          t.columns(o.show).visible(!0, !1),
            t.columns(o.hide).visible(!1, !1),
            t.columns.adjust();
        },
        show: [],
        hide: [],
      },
    }),
    e
  );
});
