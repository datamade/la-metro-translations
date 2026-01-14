from wagtail import blocks


class TitledBlock(blocks.StructBlock):
    title = blocks.CharBlock(
        required=False, help_text="Specify a title for this block. (Optional)"
    )
    description = blocks.RichTextBlock(
        required=False, help_text="Specify a description for this block. (Optional)"
    )


class ReactBlock(TitledBlock):
    def get_context(self, *args, **kwargs):
        context = super().get_context(*args, **kwargs)
        # Add additional context for your template, if needed.
        return context

    class Meta:
        template = "la_metro_translations/blocks/react_block.html"
        icon = "code"
