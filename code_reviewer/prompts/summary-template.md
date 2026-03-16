{% if issue_refs %}
#### Linked issues

{% for url in issue_refs %}
- {{ url }}
{% endfor %}

{% endif %}
#### Description

{{ description }}
