
import typing as t


def unpack_type_hint(hint: t.Any) -> t.Tuple[t.Optional[t.Any], t.List[t.Any]]:
  """
  Unpacks a type hint into it's origin type and parameters.
  """

  if isinstance(hint, t._AnnotatedAlias):  # type: ignore
    return t.Annotated, list((hint.__origin__,) + hint.__metadata__)  # type: ignore

  if isinstance(hint, t._GenericAlias):  # type: ignore
    return hint.__origin__, list(hint.__args__)

  if isinstance(hint, t._SpecialGenericAlias):  # type: ignore
    return hint.__origin__, []

  if isinstance(hint, type):
    return hint, []

  if isinstance(hint, t._SpecialForm):
    return hint, []

  return None, []