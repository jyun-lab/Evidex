ODD_ROW_TAG = "row_odd"
EVEN_ROW_TAG = "row_even"


def configure_treeview_rows(tree, dark=False):
    if dark:
        odd = "#222629"
        even = "#2B3035"
    else:
        odd = "#FFFFFF"
        even = "#F6F8FA"
    tree.tag_configure(ODD_ROW_TAG, background=odd)
    tree.tag_configure(EVEN_ROW_TAG, background=even)


def stripe_tag(index):
    return EVEN_ROW_TAG if index % 2 else ODD_ROW_TAG
