import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def policy():
    spec = importlib.util.spec_from_file_location('pr_policy', Path(__file__).resolve().parent.parent / 'scripts/pr_policy.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def event(base='main', head='develop', owner='piwas-21/cs2-apple-silicon'):
    return {'pull_request': {'base': {'ref': base, 'repo': {'full_name': 'piwas-21/cs2-apple-silicon'}},
                             'head': {'ref': head, 'repo': {'full_name': owner}}}}


def test_feature_changes_and_fork_contributions_can_target_develop(policy):
    policy.validate(event(base='develop', head='fix', owner='contributor/fork'))
    policy.validate({})


@pytest.mark.parametrize('head,owner', [('feature', 'piwas-21/cs2-apple-silicon'), ('develop', 'contributor/fork')])
def test_main_refuses_direct_feature_or_fork_promotions(policy, head, owner):
    with pytest.raises(ValueError):
        policy.validate(event(head=head, owner=owner))


@pytest.mark.parametrize('checks', [[], [{'name': 'SonarQube analysis', 'conclusion': 'failure', 'app': {'slug': 'github-actions'}}],
    [{'name': 'SonarQube analysis', 'conclusion': 'success', 'app': {'slug': 'other-app'}}]])
def test_promotion_requires_a_successful_analysis_from_the_expected_app(policy, checks):
    with pytest.raises(ValueError):
        policy.validate(event(), checks)


def test_validated_develop_can_be_promoted(policy):
    policy.validate(event(), [{'name': 'SonarQube analysis', 'conclusion': 'success', 'app': {'slug': 'github-actions'}}])
